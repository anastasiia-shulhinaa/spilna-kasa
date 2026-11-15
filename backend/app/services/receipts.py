"""Поділ чека за позиціями: кожен платить за те, що замовляв."""

from collections.abc import Sequence

from app.services.money import split_equal

ItemSpec = tuple[int, Sequence[int]]  # (ціна позиції в копійках, id учасників, які її позначили)


def preview_split(items: Sequence[ItemSpec]) -> tuple[dict[int, int], int]:
    """Проміжний підсумок: скільки вже припадає на кожного і яка сума ще не розібрана.

    Спільну позицію (наприклад, сирну тарілку на трьох) ділимо порівну між тими,
    хто її позначив; залишок копійок — за правилом split_equal.
    """
    totals: dict[int, int] = {}
    unclaimed = 0
    for price, claimants in items:
        if not claimants:
            unclaimed += price
            continue
        for uid, kop in split_equal(price, list(claimants)).items():
            totals[uid] = totals.get(uid, 0) + kop
    return dict(sorted(totals.items())), unclaimed


def split_by_items(items: Sequence[ItemSpec]) -> dict[int, int]:
    """Остаточний поділ для закриття чека. Кожна позиція повинна мати хоча б одного «власника»."""
    if not items:
        raise ValueError("У чеку немає позицій")
    totals, unclaimed = preview_split(items)
    if unclaimed:
        raise ValueError("Не всі позиції чека розібрані — кожна позиція має бути чиєюсь")
    return totals
