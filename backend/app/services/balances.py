"""Розрахунок балансів і боргів. Чисті функції без доступу до БД — їх легко тестувати."""

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OpView:
    """Спрощене подання операції для розрахунків."""

    type: str  # "expense" | "transfer"
    amount_kop: int
    payer_id: int
    recipient_id: int | None = None
    shares: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Debt:
    from_id: int
    to_id: int
    amount_kop: int


def compute_balances(ops: Iterable[OpView], member_ids: Iterable[int] = ()) -> dict[int, int]:
    """Баланс кожного учасника: додатний — йому винні, від'ємний — винен він.

    Витрата: платник отримує +сума, кожен учасник поділу −своя частка.
    Переказ A→B (повернення боргу): A +сума, B −сума.
    Сума всіх балансів завжди дорівнює 0.
    """
    balances: dict[int, int] = {uid: 0 for uid in member_ids}
    for op in ops:
        if op.type == "expense":
            balances[op.payer_id] = balances.get(op.payer_id, 0) + op.amount_kop
            for uid, share in op.shares.items():
                balances[uid] = balances.get(uid, 0) - share
        elif op.type == "transfer":
            if op.recipient_id is None:
                raise ValueError("Переказ повинен мати отримувача")
            balances[op.payer_id] = balances.get(op.payer_id, 0) + op.amount_kop
            balances[op.recipient_id] = balances.get(op.recipient_id, 0) - op.amount_kop
        else:
            raise ValueError(f"Невідомий тип операції: {op.type}")
    return balances


EXACT_LIMIT = 16  # до стількох учасників із ненульовим балансом мінімум рахується точно


def settle(balances: dict[int, int]) -> tuple[list[Debt], bool]:
    """План переказів «хто кому скільки винен» і ознака, чи доведено, що він мінімальний (D07).

    Мінімальна кількість переказів = n − k, де n — учасники з ненульовим балансом,
    а k — найбільша кількість груп, на які їх можна розбити так, щоб у кожній групі
    сума балансів дорівнювала 0 (усередині групи з m людей вистачає m − 1 переказів).
    k шукаємо динамічним програмуванням по підмножинах (O(2^n · n)) з мемоізацією сум.
    Для більших груп повертаємо жадібний план і позначаємо його як не доведено мінімальний.
    """
    if sum(balances.values()) != 0:
        raise ValueError("Сума балансів повинна дорівнювати 0")

    people = sorted(uid for uid, bal in balances.items() if bal != 0)
    n = len(people)
    if n == 0:
        return [], True
    if n > EXACT_LIMIT:
        return _greedy(balances), False

    values = [balances[uid] for uid in people]
    size = 1 << n
    subset_sum = [0] * size
    for mask in range(1, size):
        low = mask & -mask
        subset_sum[mask] = subset_sum[mask ^ low] + values[low.bit_length() - 1]

    # best[mask] — найбільша кількість «нульових» груп, якщо додавати людей з mask по одному
    best = [0] * size
    for mask in range(1, size):
        top, rest = 0, mask
        while rest:
            low = rest & -rest
            if best[mask ^ low] > top:
                top = best[mask ^ low]
            rest ^= low
        best[mask] = top + (subset_sum[mask] == 0)

    # Відновлюємо порядок додавання; при рівноцінних варіантах — стабільний вибір за id
    order: list[int] = []
    mask = size - 1
    while mask:
        target = best[mask] - (subset_sum[mask] == 0)
        for i in range(n - 1, -1, -1):
            bit = 1 << i
            if mask & bit and best[mask ^ bit] == target:
                order.append(i)
                mask ^= bit
                break
    order.reverse()

    debts: list[Debt] = []
    group: dict[int, int] = {}
    running = 0
    for i in order:
        group[people[i]] = values[i]
        running += values[i]
        if running == 0:
            debts.extend(_greedy(group))
            group = {}
    debts.sort(key=lambda d: (-d.amount_kop, d.from_id, d.to_id))
    return debts, True


def minimize_transfers(balances: dict[int, int]) -> list[Debt]:
    """Мінімальний список переказів (для груп до EXACT_LIMIT людей із боргами)."""
    return settle(balances)[0]


def _greedy(balances: dict[int, int]) -> list[Debt]:
    """Жадібне зіставлення найбільшого боржника з найбільшим кредитором. Не гарантує мінімуму."""
    creditors = [[uid, bal] for uid, bal in balances.items() if bal > 0]
    debtors = [[uid, -bal] for uid, bal in balances.items() if bal < 0]
    debts: list[Debt] = []

    while creditors and debtors:
        creditors.sort(key=lambda x: (-x[1], x[0]))
        debtors.sort(key=lambda x: (-x[1], x[0]))
        creditor, debtor = creditors[0], debtors[0]
        amount = min(creditor[1], debtor[1])
        debts.append(Debt(from_id=debtor[0], to_id=creditor[0], amount_kop=amount))
        creditor[1] -= amount
        debtor[1] -= amount
        if creditor[1] == 0:
            creditors.pop(0)
        if debtor[1] == 0:
            debtors.pop(0)
    return debts


def total_expenses(ops: Iterable[OpView]) -> int:
    """Загальні витрати групи. Перекази між учасниками не є витратами."""
    return sum(op.amount_kop for op in ops if op.type == "expense")
