"""Інтеграційні тести: повний HTTP-цикл через FastAPI + SQLAlchemy + SQLite."""

from tests.conftest import register


# ---------- Автентифікація ----------
def test_register_and_get_profile(client):
    user = register(client, "Ivanna")
    r = client.get("/api/users/me", headers=user["headers"])
    assert r.status_code == 200
    assert r.json()["display_name"] == "Ivanna"


def test_duplicate_email_is_rejected(client):
    register(client, "Ivanna")
    r = client.post(
        "/api/auth/register", json={"email": "ivanna@test.ua", "password": "secret123", "display_name": "X"}
    )
    assert r.status_code == 409


def test_login_success_and_wrong_password(client):
    register(client, "Sofia")
    ok = client.post("/api/auth/login", json={"email": "sofia@test.ua", "password": "secret123"})
    bad = client.post("/api/auth/login", json={"email": "sofia@test.ua", "password": "nope"})
    assert ok.status_code == 200 and "access_token" in ok.json()
    assert bad.status_code == 401


def test_protected_endpoint_requires_token(client):
    assert client.get("/api/groups").status_code == 401


def test_update_display_name(client):
    user = register(client, "Maryna")
    r = client.patch("/api/users/me", json={"display_name": "Марина"}, headers=user["headers"])
    assert r.status_code == 200 and r.json()["display_name"] == "Марина"


# ---------- Групи ----------
def test_create_group_and_join_by_code(client, trio):
    r = client.get(f"/api/groups/{trio['group']['id']}", headers=trio["sofia"]["headers"])
    assert r.status_code == 200
    assert [m["display_name"] for m in r.json()["members"]] == ["Ivanna", "Sofia", "Maryna"]
    assert r.json()["members"][0]["role"] == "owner"


def test_join_is_case_insensitive(client):
    owner, guest = register(client, "Owner"), register(client, "Guest")
    g = client.post("/api/groups", json={"name": "Поїздка"}, headers=owner["headers"]).json()
    r = client.post("/api/groups/join", json={"invite_code": g["invite_code"].lower()}, headers=guest["headers"])
    assert r.status_code == 200


def test_repeated_join_is_rejected(client, trio):
    r = client.post(
        "/api/groups/join", json={"invite_code": trio["group"]["invite_code"]}, headers=trio["sofia"]["headers"]
    )
    assert r.status_code == 409
    assert len(client.get(f"/api/groups/{trio['group']['id']}", headers=trio["sofia"]["headers"]).json()["members"]) == 3


def test_unknown_invite_code(client):
    user = register(client, "Ivanna")
    assert client.post("/api/groups/join", json={"invite_code": "ZZZZZZ"}, headers=user["headers"]).status_code == 404


def test_group_list_contains_only_my_groups(client, trio):
    stranger = register(client, "Stranger")
    client.post("/api/groups", json={"name": "Чужа"}, headers=stranger["headers"])
    names = [g["name"] for g in client.get("/api/groups", headers=trio["ivanna"]["headers"]).json()]
    assert names == ["Квартира"]


# ---------- Доступ (N01) ----------
def test_stranger_cannot_read_group_operations_or_balances(client, trio):
    stranger = register(client, "Stranger")
    gid = trio["group"]["id"]
    for path in (f"/api/groups/{gid}", f"/api/groups/{gid}/operations", f"/api/groups/{gid}/balances"):
        r = client.get(path, headers=stranger["headers"])
        assert r.status_code == 403, path
        assert r.json()["detail"] == "Немає доступу до групи"


def test_stranger_cannot_add_expense(client, trio):
    stranger = register(client, "Stranger")
    r = client.post(
        f"/api/groups/{trio['group']['id']}/expenses",
        json={"amount_kop": 1000, "payer_id": stranger["id"], "participant_ids": [stranger["id"]]},
        headers=stranger["headers"],
    )
    assert r.status_code == 403


# ---------- Операції та валідація ----------
def _expense(client, trio, amount_kop, participants=None, payer=None):
    ids = participants or [trio[n]["id"] for n in ("ivanna", "sofia", "maryna")]
    return client.post(
        f"/api/groups/{trio['group']['id']}/expenses",
        json={
            "amount_kop": amount_kop,
            "payer_id": payer or trio["ivanna"]["id"],
            "participant_ids": ids,
            "category": "Продукти",
            "description": "Продукти",
        },
        headers=trio["ivanna"]["headers"],
    )


def test_expense_600_creates_three_equal_shares(client, trio):
    r = _expense(client, trio, 60000)
    assert r.status_code == 201
    assert sorted(s["share_kop"] for s in r.json()["shares"]) == [20000, 20000, 20000]


def test_expense_100_by_3_shares_sum_to_amount(client, trio):
    shares = [s["share_kop"] for s in _expense(client, trio, 10000).json()["shares"]]
    assert sorted(shares, reverse=True) == [3334, 3333, 3333]


def test_zero_or_negative_amount_is_rejected(client, trio):
    for amount in (0, -100):
        r = _expense(client, trio, amount)
        assert r.status_code == 422
        assert r.json()["detail"] == "Сума має бути більшою за 0"


def test_payer_must_be_group_member(client, trio):
    stranger = register(client, "Stranger")
    assert _expense(client, trio, 1000, payer=stranger["id"]).status_code == 400


def test_participant_must_be_group_member(client, trio):
    stranger = register(client, "Stranger")
    assert _expense(client, trio, 1000, participants=[trio["ivanna"]["id"], stranger["id"]]).status_code == 400


def test_transfer_to_self_is_rejected(client, trio):
    me = trio["sofia"]
    r = client.post(
        f"/api/groups/{trio['group']['id']}/transfers",
        json={"from_user_id": me["id"], "to_user_id": me["id"], "amount_kop": 100},
        headers=me["headers"],
    )
    assert r.status_code == 400


# ---------- Повний контрольний сценарій ----------
def test_control_scenario_600_then_repay_200(client, trio):
    gid, iv, so, ma = trio["group"]["id"], trio["ivanna"], trio["sofia"], trio["maryna"]
    assert _expense(client, trio, 60000).status_code == 201

    b = client.get(f"/api/groups/{gid}/balances", headers=so["headers"]).json()
    by_id = {m["user"]["id"]: m["balance_kop"] for m in b["members"]}
    assert by_id == {iv["id"]: 40000, so["id"]: -20000, ma["id"]: -20000}
    assert len(b["debts"]) == 2

    r = client.post(
        f"/api/groups/{gid}/transfers",
        json={"from_user_id": so["id"], "to_user_id": iv["id"], "amount_kop": 20000},
        headers=so["headers"],
    )
    assert r.status_code == 201

    b = client.get(f"/api/groups/{gid}/balances", headers=so["headers"]).json()
    by_id = {m["user"]["id"]: m["balance_kop"] for m in b["members"]}
    assert by_id[so["id"]] == 0
    assert b["total_expenses_kop"] == 60000
    assert [(d["from_user"]["id"], d["to_user"]["id"], d["amount_kop"]) for d in b["debts"]] == [
        (ma["id"], iv["id"], 20000)
    ]

    ops = client.get(f"/api/groups/{gid}/operations", headers=ma["headers"]).json()
    assert [o["type"] for o in ops] == ["transfer", "expense"]
    group = client.get(f"/api/groups/{gid}", headers=iv["headers"]).json()
    assert group["my_balance_kop"] == 20000
