"""Інтеграційні тести: точні суми, чеки з позиціями та фото, експорт, видалення операцій."""

from io import BytesIO

import pytest
from openpyxl import load_workbook

from tests.conftest import png_bytes, register

PNG = png_bytes()


@pytest.fixture()
def restaurant(client):
    """Марина, Іванна та Настя в групі «Карпати»."""
    maryna, ivanna, nastia = (register(client, n) for n in ("Maryna", "Ivanna", "Nastia"))
    g = client.post("/api/groups", json={"name": "Карпати"}, headers=maryna["headers"]).json()
    for p in (ivanna, nastia):
        client.post("/api/groups/join", json={"invite_code": g["invite_code"]}, headers=p["headers"])
    return {"gid": g["id"], "maryna": maryna, "ivanna": ivanna, "nastia": nastia}


def balances(client, r, who="maryna"):
    data = client.get(f"/api/groups/{r['gid']}/balances", headers=r[who]["headers"]).json()
    return {m["user"]["id"]: m["balance_kop"] for m in data["members"]}, data


# ---------- Точні суми ----------
def test_exact_split_restaurant_1500(client, restaurant):
    r = restaurant
    resp = client.post(
        f"/api/groups/{r['gid']}/expenses",
        json={
            "amount_kop": 150000,
            "payer_id": r["maryna"]["id"],
            "split_mode": "exact",
            "category": "Розваги",
            "description": "Ресторан",
            "shares": [
                {"user_id": r["ivanna"]["id"], "share_kop": 60000},
                {"user_id": r["nastia"]["id"], "share_kop": 30000},
                {"user_id": r["maryna"]["id"], "share_kop": 60000},
            ],
        },
        headers=r["maryna"]["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["split_mode"] == "exact"
    b, data = balances(client, r)
    assert b == {r["maryna"]["id"]: 90000, r["ivanna"]["id"]: -60000, r["nastia"]["id"]: -30000}
    assert data["total_expenses_kop"] == 150000


def test_exact_split_mismatch_is_rejected(client, restaurant):
    r = restaurant
    resp = client.post(
        f"/api/groups/{r['gid']}/expenses",
        json={
            "amount_kop": 150000,
            "payer_id": r["maryna"]["id"],
            "split_mode": "exact",
            "shares": [{"user_id": r["ivanna"]["id"], "share_kop": 60000}],
        },
        headers=r["maryna"]["headers"],
    )
    assert resp.status_code == 400
    assert "залишилось розподілити 900,00" in resp.json()["detail"]


def test_exact_split_without_shares_is_rejected(client, restaurant):
    r = restaurant
    resp = client.post(
        f"/api/groups/{r['gid']}/expenses",
        json={"amount_kop": 1000, "payer_id": r["maryna"]["id"], "split_mode": "exact"},
        headers=r["maryna"]["headers"],
    )
    assert resp.status_code == 422


# ---------- Чек: позиції, «що я замовляла», закриття ----------
def make_receipt(client, r):
    resp = client.post(
        f"/api/groups/{r['gid']}/receipts",
        json={
            "title": "Гуцульська хата",
            "payer_id": r["maryna"]["id"],
            "category": "Розваги",
            "items": [
                {"name": "Бограч", "price_kop": 32000},
                {"name": "Вареники", "price_kop": 16000},
                {"name": "Банош", "price_kop": 28000},
                {"name": "Сирна тарілка", "price_kop": 27000},
            ],
        },
        headers=r["maryna"]["headers"],
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def claim(client, r, who, receipt, names):
    ids = [i["id"] for i in receipt["items"] if i["name"] in names]
    return client.put(
        f"/api/groups/{r['gid']}/receipts/{receipt['id']}/claims", json={"item_ids": ids}, headers=r[who]["headers"]
    )


def test_receipt_full_flow(client, restaurant):
    r = restaurant
    rc = make_receipt(client, r)
    assert rc["total_kop"] == 103000 and rc["unclaimed_kop"] == 103000

    claim(client, r, "ivanna", rc, {"Бограч", "Сирна тарілка"})
    claim(client, r, "nastia", rc, {"Вареники", "Сирна тарілка"})
    after = claim(client, r, "maryna", rc, {"Банош", "Сирна тарілка"}).json()
    assert after["unclaimed_kop"] == 0
    totals = {t["user_id"]: t["share_kop"] for t in after["totals"]}
    assert totals == {r["maryna"]["id"]: 37000, r["ivanna"]["id"]: 41000, r["nastia"]["id"]: 25000}

    op = client.post(f"/api/groups/{r['gid']}/receipts/{rc['id']}/finalize", headers=r["maryna"]["headers"])
    assert op.status_code == 201
    assert op.json()["split_mode"] == "items" and op.json()["receipt_id"] == rc["id"]

    b, _ = balances(client, r)
    assert b[r["ivanna"]["id"]] == -41000 and b[r["nastia"]["id"]] == -25000 and b[r["maryna"]["id"]] == 66000

    # Після закриття змінювати позначки не можна
    assert claim(client, r, "ivanna", rc, {"Бограч"}).status_code == 409


def test_claims_can_be_changed_while_open(client, restaurant):
    r = restaurant
    rc = make_receipt(client, r)
    claim(client, r, "ivanna", rc, {"Бограч", "Банош"})
    again = claim(client, r, "ivanna", rc, {"Бограч"}).json()
    by_name = {i["name"]: i["claimed_by"] for i in again["items"]}
    assert by_name["Бограч"] == [r["ivanna"]["id"]] and by_name["Банош"] == []


def test_finalize_requires_all_items_claimed(client, restaurant):
    r = restaurant
    rc = make_receipt(client, r)
    claim(client, r, "ivanna", rc, {"Бограч"})
    resp = client.post(f"/api/groups/{r['gid']}/receipts/{rc['id']}/finalize", headers=r["maryna"]["headers"])
    assert resp.status_code == 400


def test_only_payer_or_author_can_finalize(client, restaurant):
    r = restaurant
    rc = make_receipt(client, r)
    for who in ("ivanna", "nastia", "maryna"):
        claim(client, r, who, rc, {"Бограч", "Вареники", "Банош", "Сирна тарілка"})
    resp = client.post(f"/api/groups/{r['gid']}/receipts/{rc['id']}/finalize", headers=r["ivanna"]["headers"])
    assert resp.status_code == 403


def test_claim_unknown_item_rejected(client, restaurant):
    r = restaurant
    rc = make_receipt(client, r)
    resp = client.put(
        f"/api/groups/{r['gid']}/receipts/{rc['id']}/claims", json={"item_ids": [99999]}, headers=r["ivanna"]["headers"]
    )
    assert resp.status_code == 400


# ---------- Фото чека ----------
def test_photo_upload_and_download(client, restaurant):
    r = restaurant
    rc = make_receipt(client, r)
    up = client.post(
        f"/api/groups/{r['gid']}/receipts/{rc['id']}/photo",
        files={"file": ("check.png", PNG, "image/png")},
        headers=r["maryna"]["headers"],
    )
    assert up.status_code == 200 and up.json()["has_photo"] is True
    got = client.get(f"/api/groups/{r['gid']}/receipts/{rc['id']}/photo", headers=r["ivanna"]["headers"])
    assert got.status_code == 200 and got.content == PNG and got.headers["content-type"] == "image/png"


def test_photo_rejects_non_image(client, restaurant):
    r = restaurant
    rc = make_receipt(client, r)
    resp = client.post(
        f"/api/groups/{r['gid']}/receipts/{rc['id']}/photo",
        files={"file": ("evil.png", b"<script>alert(1)</script>", "image/png")},
        headers=r["maryna"]["headers"],
    )
    assert resp.status_code == 400


def test_stranger_cannot_see_receipt_or_photo(client, restaurant):
    r = restaurant
    rc = make_receipt(client, r)
    stranger = register(client, "Stranger")
    for path in (f"/receipts/{rc['id']}", f"/receipts/{rc['id']}/photo", "/receipts"):
        assert client.get(f"/api/groups/{r['gid']}{path}", headers=stranger["headers"]).status_code == 403


# ---------- Експорт в Excel ----------
def test_export_xlsx(client, restaurant):
    r = restaurant
    client.post(
        f"/api/groups/{r['gid']}/expenses",
        json={"amount_kop": 90000, "payer_id": r["maryna"]["id"], "participant_ids": [r[n]["id"] for n in ("maryna", "ivanna", "nastia")]},
        headers=r["maryna"]["headers"],
    )
    resp = client.get(f"/api/groups/{r['gid']}/export.xlsx", headers=r["nastia"]["headers"])
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "filename*=UTF-8''" in resp.headers["content-disposition"]
    wb = load_workbook(BytesIO(resp.content))
    assert wb["Операції"].cell(2, 8).value == 900


# ---------- Видалення операції ----------
def test_delete_operation_restores_balances(client, restaurant):
    r = restaurant
    op = client.post(
        f"/api/groups/{r['gid']}/expenses",
        json={"amount_kop": 30000, "payer_id": r["ivanna"]["id"], "participant_ids": [r["ivanna"]["id"], r["nastia"]["id"]]},
        headers=r["ivanna"]["headers"],
    ).json()
    assert client.delete(f"/api/groups/{r['gid']}/operations/{op['id']}", headers=r["nastia"]["headers"]).status_code == 403
    assert client.delete(f"/api/groups/{r['gid']}/operations/{op['id']}", headers=r["ivanna"]["headers"]).status_code == 204
    b, data = balances(client, r)
    assert set(b.values()) == {0} and data["total_expenses_kop"] == 0


def test_delete_receipt_expense_reopens_receipt(client, restaurant):
    r = restaurant
    rc = make_receipt(client, r)
    claim(client, r, "maryna", rc, {"Бограч", "Вареники", "Банош", "Сирна тарілка"})
    op = client.post(f"/api/groups/{r['gid']}/receipts/{rc['id']}/finalize", headers=r["maryna"]["headers"]).json()
    client.delete(f"/api/groups/{r['gid']}/operations/{op['id']}", headers=r["maryna"]["headers"])
    reopened = client.get(f"/api/groups/{r['gid']}/receipts/{rc['id']}", headers=r["ivanna"]["headers"]).json()
    assert reopened["status"] == "open" and reopened["operation_id"] is None
    assert claim(client, r, "ivanna", rc, {"Бограч"}).status_code == 200
