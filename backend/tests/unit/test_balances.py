import pytest

from app.services.balances import Debt, OpView, compute_balances, minimize_transfers, total_expenses
from app.services.money import split_equal

IVANNA, SOFIA, MARYNA = 1, 2, 3


def expense(payer: int, amount: int, ids: list[int]) -> OpView:
    return OpView(type="expense", amount_kop=amount, payer_id=payer, shares=split_equal(amount, ids))


def transfer(frm: int, to: int, amount: int) -> OpView:
    return OpView(type="transfer", amount_kop=amount, payer_id=frm, recipient_id=to)


def test_control_scenario_600_for_three():
    """Іванна платить 600 за трьох: їй винні 400, Софія й Марина винні по 200."""
    balances = compute_balances([expense(IVANNA, 60000, [IVANNA, SOFIA, MARYNA])])
    assert balances == {IVANNA: 40000, SOFIA: -20000, MARYNA: -20000}


def test_repayment_clears_sofia_debt():
    ops = [expense(IVANNA, 60000, [IVANNA, SOFIA, MARYNA]), transfer(SOFIA, IVANNA, 20000)]
    balances = compute_balances(ops)
    assert balances[SOFIA] == 0
    assert balances[IVANNA] == 20000
    assert balances[MARYNA] == -20000


def test_transfer_is_not_an_expense():
    """Після повернення 200 витрати групи залишаються 600, а не 800."""
    ops = [expense(IVANNA, 60000, [IVANNA, SOFIA, MARYNA]), transfer(SOFIA, IVANNA, 20000)]
    assert total_expenses(ops) == 60000


def test_balances_always_sum_to_zero():
    ops = [
        expense(IVANNA, 10000, [IVANNA, SOFIA, MARYNA]),
        expense(SOFIA, 777, [SOFIA, MARYNA]),
        expense(MARYNA, 50001, [IVANNA, SOFIA, MARYNA]),
        transfer(SOFIA, MARYNA, 1234),
    ]
    assert sum(compute_balances(ops).values()) == 0


def test_members_without_operations_have_zero_balance():
    assert compute_balances([], member_ids=[IVANNA, SOFIA]) == {IVANNA: 0, SOFIA: 0}


def test_transfer_without_recipient_is_rejected():
    with pytest.raises(ValueError):
        compute_balances([OpView(type="transfer", amount_kop=100, payer_id=IVANNA)])


def test_minimize_transfers_control_scenario():
    debts = minimize_transfers({IVANNA: 40000, SOFIA: -20000, MARYNA: -20000})
    assert debts == [Debt(SOFIA, IVANNA, 20000), Debt(MARYNA, IVANNA, 20000)]


def test_minimize_transfers_collapses_chain():
    """Ланцюжок A винен B 100, B винен C 100 → достатньо одного переказу A → C."""
    ops = [expense(2, 10000, [1]), expense(3, 10000, [2])]
    debts = minimize_transfers(compute_balances(ops))
    assert debts == [Debt(from_id=1, to_id=3, amount_kop=10000)]


def test_minimize_transfers_settled_group_has_no_debts():
    assert minimize_transfers({IVANNA: 0, SOFIA: 0}) == []


def test_minimize_transfers_count_is_at_most_n_minus_1():
    balances = {1: 5000, 2: 3000, 3: -1000, 4: -2000, 5: -5000}
    debts = minimize_transfers(balances)
    assert len(debts) <= len(balances) - 1
    paid = {uid: 0 for uid in balances}
    for d in debts:
        paid[d.from_id] += d.amount_kop
        paid[d.to_id] -= d.amount_kop
    assert all(paid[uid] == -bal for uid, bal in balances.items())


def test_settle_counterexample_needs_4_not_5_transfers():
    """Контрприклад D07: жадібний алгоритм давав 5 переказів, мінімум — 4."""
    from app.services.balances import _greedy, settle

    balances = {1: 10000, 2: 9000, 3: 4000, 4: -9000, 5: -8000, 6: -6000}
    debts, optimal = settle(balances)
    assert optimal and len(debts) == 4 and len(_greedy(balances)) == 5
    rest = dict(balances)
    for d in debts:
        rest[d.from_id] += d.amount_kop
        rest[d.to_id] -= d.amount_kop
    assert set(rest.values()) == {0}


def test_settle_large_group_falls_back_and_says_so():
    from app.services.balances import EXACT_LIMIT, settle

    n = EXACT_LIMIT + 2
    balances = {i: 100 for i in range(1, n)}
    balances[n] = -100 * (n - 1)
    debts, optimal = settle(balances)
    assert optimal is False and len(debts) == n - 1


def test_minimize_transfers_rejects_unbalanced_input():
    with pytest.raises(ValueError):
        minimize_transfers({IVANNA: 100, SOFIA: -50})
