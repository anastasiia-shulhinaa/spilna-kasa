"""Регресійні тести до звіту «Спільна каса — помилки в коді» (D01–D08) і нових функцій."""

import threading
import time
from datetime import date

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.config import DEV_JWT_SECRET, ConfigError, Settings, validate_settings
from app.models import Operation, Receipt, ReceiptItem
from app.services.money import MAX_AMOUNT_KOP
from tests.conftest import png_bytes, register


def setup_group(client, names=("Maryna", "Ivanna", "Nastia")):
    people = {n.lower(): register(client, n) for n in names}
    first = people[names[0].lower()]
    g = client.post("/api/groups", json={"name": "Карпати"}, headers=first["headers"]).json()
    for key, p in people.items():
        if p is not first:
            client.post("/api/groups/join", json={"invite_code": g["invite_code"]}, headers=p["headers"])
    return g["id"], people


def make_receipt(client, gid, owner, payer_id=None, items=None):
    r = client.post(
        f"/api/groups/{gid}/receipts",
        json={
            "title": "Колиба",
            "payer_id": payer_id or owner["id"],
            "items": items or [{"name": "Бограч", "price_kop": 32000}, {"name": "Узвар", "price_kop": 8000}],
        },
        headers=owner["headers"],
    )
    assert r.status_code == 201, r.text
    return r.json()


def claim_all(client, gid, receipt, person):
    return client.put(
        f"/api/groups/{gid}/receipts/{receipt['id']}/claims",
        json={"item_ids": [i["id"] for i in receipt["items"]]},
        headers=person["headers"],
    )


# ---------------- D01: цілісність зв'язку чека й операції ----------------
@pytest.fixture()
def closed_receipt(file_db):
    client, factory = file_db
    gid, p = setup_group(client)
    rc = make_receipt(client, gid, p["maryna"])
    claim_all(client, gid, rc, p["maryna"])
    op = client.post(f"/api/groups/{gid}/receipts/{rc['id']}/finalize", headers=p["maryna"]["headers"]).json()
    return client, factory, gid, p, rc, op


def _raw(factory, sql, **params):
    with factory() as s:
        s.execute(text(sql), params)
        s.commit()


def test_d01_second_receipt_for_same_operation_rejected(closed_receipt):
    _, factory, gid, p, _, op = closed_receipt
    with pytest.raises(IntegrityError):
        _raw(
            factory,
            "INSERT INTO receipts (group_id, title, category, payer_id, created_by, status, operation_id, op_date, created_at)"
            " VALUES (:g, 'Дубль', 'Інше', :u, :u, 'closed', :op, '2026-11-15', '2026-11-15')",
            g=gid, u=p["maryna"]["id"], op=op["id"],
        )


def test_d01_link_to_operation_of_other_group_rejected(closed_receipt):
    client, factory, _, p, _, op = closed_receipt
    other = client.post("/api/groups", json={"name": "Інша"}, headers=p["maryna"]["headers"]).json()
    with pytest.raises(IntegrityError):
        _raw(
            factory,
            "INSERT INTO receipts (group_id, title, category, payer_id, created_by, status, operation_id, op_date, created_at)"
            " VALUES (:g, 'Чужий', 'Інше', :u, :u, 'closed', :op, '2026-11-15', '2026-11-15')",
            g=other["id"], u=p["maryna"]["id"], op=op["id"],
        )


def test_d01_inconsistent_status_and_link_rejected(closed_receipt):
    _, factory, _, _, rc, _ = closed_receipt
    with pytest.raises(IntegrityError):
        _raw(factory, "UPDATE receipts SET operation_id = NULL WHERE id = :r", r=rc["id"])  # closed без операції


def test_d01_deleting_operation_directly_in_db_is_blocked(closed_receipt):
    _, factory, _, _, _, op = closed_receipt
    with pytest.raises(IntegrityError):
        _raw(factory, "DELETE FROM operations WHERE id = :o", o=op["id"])


def test_d01_delete_via_api_reopens_receipt_and_keeps_claims(closed_receipt):
    client, _, gid, p, rc, op = closed_receipt
    assert client.delete(f"/api/groups/{gid}/operations/{op['id']}", headers=p["maryna"]["headers"]).status_code == 204
    again = client.get(f"/api/groups/{gid}/receipts/{rc['id']}", headers=p["maryna"]["headers"]).json()
    assert again["status"] == "open" and again["operation_id"] is None
    assert all(i["claimed_by"] == [p["maryna"]["id"]] for i in again["items"])


# ---------------- D02: одночасні дії з чеком ----------------
def _parallel(*calls):
    results = [None] * len(calls)

    def run(i, fn):
        results[i] = fn()

    threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(calls)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


@pytest.fixture()
def slow_split(monkeypatch):
    """Розширює вікно перегонів: розрахунок часток триває 0,3 с."""
    import app.routers.receipts as rr

    original = rr.split_by_items

    def slow(spec):
        time.sleep(0.3)
        return original(spec)

    monkeypatch.setattr(rr, "split_by_items", slow)


def test_d02_parallel_finalize_creates_exactly_one_expense(file_db, slow_split):
    client, factory = file_db
    gid, p = setup_group(client)
    rc = make_receipt(client, gid, p["maryna"])
    claim_all(client, gid, rc, p["maryna"])
    url = f"/api/groups/{gid}/receipts/{rc['id']}/finalize"
    a, b = _parallel(lambda: client.post(url, headers=p["maryna"]["headers"]), lambda: client.post(url, headers=p["maryna"]["headers"]))
    assert sorted([a.status_code, b.status_code]) == [201, 409]
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(Operation)) == 1


def test_d02_claim_and_finalize_do_not_lose_updates(file_db, slow_split):
    client, factory = file_db
    gid, p = setup_group(client)
    rc = make_receipt(client, gid, p["maryna"])
    claim_all(client, gid, rc, p["maryna"])
    fin, cl = _parallel(
        lambda: client.post(f"/api/groups/{gid}/receipts/{rc['id']}/finalize", headers=p["maryna"]["headers"]),
        lambda: (time.sleep(0.05), claim_all(client, gid, rc, p["ivanna"]))[1],
    )
    assert fin.status_code == 201
    op = fin.json()
    if cl.status_code == 200:  # позначка встигла до закриття — вона має бути у витраті
        assert {s["user_id"] for s in op["shares"]} == {p["maryna"]["id"], p["ivanna"]["id"]}
    else:  # інакше її відхилено, бо чек уже закрито
        assert cl.status_code == 409
        assert {s["user_id"] for s in op["shares"]} == {p["maryna"]["id"]}


def test_d02_delete_and_finalize_one_wins(file_db, slow_split):
    client, factory = file_db
    gid, p = setup_group(client)
    rc = make_receipt(client, gid, p["maryna"])
    claim_all(client, gid, rc, p["maryna"])
    base = f"/api/groups/{gid}/receipts/{rc['id']}"
    fin, rm = _parallel(
        lambda: client.post(f"{base}/finalize", headers=p["maryna"]["headers"]),
        lambda: (time.sleep(0.05), client.delete(base, headers=p["maryna"]["headers"]))[1],
    )
    assert (fin.status_code, rm.status_code) in {(201, 409), (404, 204)}


# ---------------- D03: порожні після обрізання назви ----------------
def test_d03_whitespace_only_names_rejected(client):
    gid, p = setup_group(client, ("Maryna", "Ivanna"))
    h = p["maryna"]["headers"]
    me_before = client.get("/api/users/me", headers=h).json()
    assert client.patch("/api/users/me", json={"display_name": "   "}, headers=h).status_code == 422
    assert client.get("/api/users/me", headers=h).json() == me_before
    assert client.post("/api/groups", json={"name": "   "}, headers=h).status_code == 422
    bad_title = {"title": "  ", "payer_id": p["maryna"]["id"], "items": [{"name": "Чай", "price_kop": 100}]}
    assert client.post(f"/api/groups/{gid}/receipts", json=bad_title, headers=h).status_code == 422
    bad_item = {"title": "Кафе", "payer_id": p["maryna"]["id"], "items": [{"name": "\t ", "price_kop": 100}]}
    resp = client.post(f"/api/groups/{gid}/receipts", json=bad_item, headers=h)
    assert resp.status_code == 422 and "порожнім" in resp.json()["detail"]
    assert client.get(f"/api/groups/{gid}/receipts", headers=h).json() == []


def test_d03_names_are_trimmed(client):
    _, p = setup_group(client, ("Maryna",))
    g = client.post("/api/groups", json={"name": "  Квартира  "}, headers=p["maryna"]["headers"]).json()
    assert g["name"] == "Квартира"


# ---------------- D04: ліміт загальної суми чека ----------------
def test_d04_receipt_total_limit(client):
    gid, p = setup_group(client, ("Maryna",))
    h, uid = p["maryna"]["headers"], p["maryna"]["id"]
    half = MAX_AMOUNT_KOP // 2
    ok = {"title": "Ок", "payer_id": uid, "items": [{"name": "А", "price_kop": half}, {"name": "Б", "price_kop": MAX_AMOUNT_KOP - half}]}
    assert client.post(f"/api/groups/{gid}/receipts", json=ok, headers=h).status_code == 201
    over = {"title": "Забагато", "payer_id": uid, "items": [{"name": "А", "price_kop": half}, {"name": "Б", "price_kop": MAX_AMOUNT_KOP - half + 1}]}
    resp = client.post(f"/api/groups/{gid}/receipts", json=over, headers=h)
    assert resp.status_code == 422 and "ліміт" in resp.json()["detail"]


def test_d04_finalize_rechecks_total(file_db):
    client, factory = file_db
    gid, p = setup_group(client, ("Maryna",))
    uid = p["maryna"]["id"]
    with factory() as s:  # «старий» або імпортований чек в обхід API
        r = Receipt(group_id=gid, title="Імпорт", category="Інше", payer_id=uid, created_by=uid, op_date=date.today(),
                    items=[ReceiptItem(name="А", price_kop=6_000_000_000, position=0), ReceiptItem(name="Б", price_kop=6_000_000_000, position=1)])
        s.add(r)
        s.commit()
        rid = r.id
    rc = client.get(f"/api/groups/{gid}/receipts/{rid}", headers=p["maryna"]["headers"]).json()
    claim_all(client, gid, rc, p["maryna"])
    resp = client.post(f"/api/groups/{gid}/receipts/{rid}/finalize", headers=p["maryna"]["headers"])
    assert resp.status_code == 400
    after = client.get(f"/api/groups/{gid}/receipts/{rid}", headers=p["maryna"]["headers"]).json()
    assert after["status"] == "open"


# ---------------- D05: чек зберігається навіть якщо фото не завантажилось ----------------
def test_d05_failed_photo_keeps_single_receipt_and_retry_works(client):
    gid, p = setup_group(client, ("Maryna",))
    h = p["maryna"]["headers"]
    rc = make_receipt(client, gid, p["maryna"])
    bad = client.post(f"/api/groups/{gid}/receipts/{rc['id']}/photo", files={"file": ("x.jpg", b"not an image", "image/jpeg")}, headers=h)
    assert bad.status_code == 400
    assert len(client.get(f"/api/groups/{gid}/receipts", headers=h).json()) == 1
    retry = client.post(f"/api/groups/{gid}/receipts/{rc['id']}/photo", files={"file": ("x.png", png_bytes(), "image/png")}, headers=h)
    assert retry.status_code == 200 and retry.json()["has_photo"]
    assert len(client.get(f"/api/groups/{gid}/receipts", headers=h).json()) == 1


# ---------------- D06: перевірка, заміна й версія фото ----------------
def _upload(client, gid, rid, data, headers, name="c.png", ctype="image/png"):
    return client.post(f"/api/groups/{gid}/receipts/{rid}/photo", files={"file": (name, data, ctype)}, headers=headers)


def test_d06_corrupted_image_rejected(client):
    gid, p = setup_group(client, ("Maryna",))
    rc = make_receipt(client, gid, p["maryna"])
    broken = png_bytes()[:60]  # правильний підпис PNG, обрізані дані
    assert _upload(client, gid, rc["id"], broken, p["maryna"]["headers"]).status_code == 400
    fake_webp = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 40
    assert _upload(client, gid, rc["id"], fake_webp, p["maryna"]["headers"], "c.webp", "image/webp").status_code == 400


def test_d06_format_detected_from_content_not_header(client):
    gid, p = setup_group(client, ("Maryna",))
    rc = make_receipt(client, gid, p["maryna"])
    up = _upload(client, gid, rc["id"], png_bytes(), p["maryna"]["headers"], "c.jpg", "image/jpeg")
    assert up.status_code == 200
    got = client.get(f"/api/groups/{gid}/receipts/{rc['id']}/photo", headers=p["maryna"]["headers"])
    assert got.headers["content-type"] == "image/png"


def test_d06_write_failure_keeps_previous_photo(client, monkeypatch):
    gid, p = setup_group(client, ("Maryna",))
    h = p["maryna"]["headers"]
    rc = make_receipt(client, gid, p["maryna"])
    first = png_bytes((10, 20, 30))
    v1 = _upload(client, gid, rc["id"], first, h).json()["photo_version"]

    from pathlib import Path

    real_write = Path.write_bytes
    monkeypatch.setattr(Path, "write_bytes", lambda self, data: (_ for _ in ()).throw(OSError("disk full")))
    assert _upload(client, gid, rc["id"], png_bytes((200, 0, 0)), h).status_code == 500
    monkeypatch.setattr(Path, "write_bytes", real_write)

    after = client.get(f"/api/groups/{gid}/receipts/{rc['id']}", headers=h).json()
    assert after["photo_version"] == v1
    assert client.get(f"/api/groups/{gid}/receipts/{rc['id']}/photo", headers=h).content == first


def test_d06_metadata_failure_keeps_previous_photo_and_cleans_new_file(client, monkeypatch, tmp_path):
    import app.routers.receipts as rr

    gid, p = setup_group(client, ("Maryna",))
    h = p["maryna"]["headers"]
    rc = make_receipt(client, gid, p["maryna"])
    first = png_bytes((10, 20, 30))
    _upload(client, gid, rc["id"], first, h)
    files_before = set((tmp_path / "uploads" / "receipts").iterdir())

    def broken(*_a, **_k):
        raise RuntimeError("commit failed")

    monkeypatch.setattr(rr, "_save_photo_metadata", broken)
    assert _upload(client, gid, rc["id"], png_bytes((0, 200, 0)), h).status_code == 500
    assert set((tmp_path / "uploads" / "receipts").iterdir()) == files_before
    assert client.get(f"/api/groups/{gid}/receipts/{rc['id']}/photo", headers=h).content == first


def test_d06_photo_version_changes_after_replacement(client):
    gid, p = setup_group(client, ("Maryna",))
    h = p["maryna"]["headers"]
    rc = make_receipt(client, gid, p["maryna"])
    v1 = _upload(client, gid, rc["id"], png_bytes((1, 1, 1)), h).json()["photo_version"]
    second = png_bytes((2, 2, 2))
    v2 = _upload(client, gid, rc["id"], second, h).json()["photo_version"]
    assert v1 and v2 and v1 != v2
    assert client.get(f"/api/groups/{gid}/receipts/{rc['id']}/photo", headers=h).content == second


# ---------------- D07: мінімальний план переказів, однаковий в API і XLSX ----------------
def test_d07_api_and_xlsx_use_minimal_plan(client):
    from io import BytesIO

    from openpyxl import load_workbook

    names = ("A", "B", "C", "D", "E", "F")
    gid, p = setup_group(client, names)
    ids = {n: p[n.lower()]["id"] for n in names}
    # Баланси з контрприкладу (у гривнях): A +100, B +90, C +40, D −90, E −80, F −60.
    # Жадібний алгоритм давав 5 переказів, мінімум — 4.
    targets = {"A": 10000, "B": 9000, "C": 4000, "D": -9000, "E": -8000, "F": -6000}
    allocation = {"A": {"E": 8000, "F": 2000}, "B": {"D": 9000}, "C": {"F": 4000}}
    for payer, parts in allocation.items():
        r = client.post(
            f"/api/groups/{gid}/expenses",
            json={"amount_kop": sum(parts.values()), "payer_id": ids[payer], "split_mode": "exact",
                  "shares": [{"user_id": ids[d], "share_kop": v} for d, v in parts.items()]},
            headers=p[payer.lower()]["headers"],
        )
        assert r.status_code == 201, r.text
    data = client.get(f"/api/groups/{gid}/balances", headers=p["a"]["headers"]).json()
    assert {m["user"]["display_name"]: m["balance_kop"] for m in data["members"]} == targets
    assert data["debts_optimal"] is True and len(data["debts"]) == 4
    rest = dict(targets)
    for d in data["debts"]:
        rest[d["from_user"]["display_name"]] += d["amount_kop"]
        rest[d["to_user"]["display_name"]] -= d["amount_kop"]
    assert set(rest.values()) == {0}

    wb = load_workbook(BytesIO(client.get(f"/api/groups/{gid}/export.xlsx", headers=p["a"]["headers"]).content))
    rows = [r for r in wb["Хто кому винен"].iter_rows(min_row=2, values_only=True) if r and r[0]]
    api_rows = [(d["from_user"]["display_name"], d["to_user"]["display_name"], d["amount_kop"] / 100) for d in data["debts"]]
    assert rows == api_rows


# ---------------- D08: секрет JWT у продакшені ----------------
def test_d08_prod_refuses_default_secret():
    with pytest.raises(ConfigError) as e:
        validate_settings(Settings(env="prod", jwt_secret=DEV_JWT_SECRET))
    assert DEV_JWT_SECRET not in str(e.value)


def test_d08_prod_refuses_short_secret():
    with pytest.raises(ConfigError):
        validate_settings(Settings(env="prod", jwt_secret="short"))


def test_d08_prod_accepts_strong_secret_and_dev_allows_default():
    validate_settings(Settings(env="prod", jwt_secret="x" * 48))
    validate_settings(Settings(env="dev", jwt_secret=DEV_JWT_SECRET))


# ---------------- Нові функції ----------------
def test_change_receipt_payer(client):
    gid, p = setup_group(client)
    rc = make_receipt(client, gid, p["maryna"])
    url = f"/api/groups/{gid}/receipts/{rc['id']}"
    assert client.patch(url, json={"payer_id": p["ivanna"]["id"]}, headers=p["nastia"]["headers"]).status_code == 403
    r = client.patch(url, json={"payer_id": p["ivanna"]["id"]}, headers=p["maryna"]["headers"])
    assert r.status_code == 200 and r.json()["payer_id"] == p["ivanna"]["id"]
    stranger = register(client, "Stranger")
    assert client.patch(url, json={"payer_id": stranger["id"]}, headers=p["maryna"]["headers"]).status_code == 400


def test_my_debts_summary_across_groups(client):
    gid, p = setup_group(client)
    m, i, n = p["maryna"], p["ivanna"], p["nastia"]
    client.post(f"/api/groups/{gid}/expenses", json={"amount_kop": 150000, "payer_id": m["id"], "split_mode": "exact",
                "shares": [{"user_id": i["id"], "share_kop": 60000}, {"user_id": n["id"], "share_kop": 30000}, {"user_id": m["id"], "share_kop": 60000}]},
                headers=m["headers"])
    g2 = client.post("/api/groups", json={"name": "Квартира"}, headers=i["headers"]).json()
    client.post("/api/groups/join", json={"invite_code": g2["invite_code"]}, headers=m["headers"])
    client.post(f"/api/groups/{g2['id']}/expenses", json={"amount_kop": 10000, "payer_id": i["id"], "participant_ids": [i["id"], m["id"]]}, headers=i["headers"])

    mine = client.get("/api/me/debts", headers=m["headers"]).json()
    assert mine["owed_to_me_total_kop"] == 90000 and mine["i_owe_total_kop"] == 5000
    assert [(r["user"]["id"], r["total_kop"]) for r in mine["owed_to_me"]] == [(i["id"], 60000), (n["id"], 30000)]
    assert mine["i_owe"][0]["user"]["id"] == i["id"] and mine["i_owe"][0]["groups"][0]["group"]["name"] == "Квартира"


def test_history_filters(client):
    gid, p = setup_group(client)
    m, i, n = p["maryna"], p["ivanna"], p["nastia"]
    client.post(f"/api/groups/{gid}/expenses", json={"amount_kop": 30000, "payer_id": m["id"], "participant_ids": [m["id"], i["id"]]}, headers=m["headers"])
    client.post(f"/api/groups/{gid}/transfers", json={"from_user_id": i["id"], "to_user_id": m["id"], "amount_kop": 15000}, headers=i["headers"])
    all_items = client.get("/api/history", headers=n["headers"]).json()
    assert [h["type"] for h in all_items] == ["transfer", "expense"]
    transfers = client.get("/api/history?kind=transfers", headers=m["headers"]).json()
    assert len(transfers) == 1 and transfers[0]["payer"]["id"] == i["id"] and transfers[0]["recipient"]["id"] == m["id"]
    assert client.get("/api/history?mine=true", headers=n["headers"]).json() == []
    assert client.get("/api/history?group_id=999", headers=m["headers"]).json() == []
