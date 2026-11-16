import pytest

from app.services.money import split_exact
from app.services.receipts import preview_split, split_by_items

MARYNA, IVANNA, NASTIA = 3, 1, 5


# ---------- Довільний поділ (точні суми) ----------
def test_exact_restaurant_1500():
    """Марина заплатила 1500: Іванна з'їла на 600, Настя на 300, сама Марина на 600."""
    shares = split_exact(150000, {IVANNA: 60000, NASTIA: 30000, MARYNA: 60000})
    assert shares == {IVANNA: 60000, MARYNA: 60000, NASTIA: 30000}


def test_exact_drops_zero_shares():
    assert split_exact(1000, {IVANNA: 1000, NASTIA: 0}) == {IVANNA: 1000}


def test_exact_rejects_sum_below_amount():
    with pytest.raises(ValueError, match="залишилось розподілити 100,00"):
        split_exact(150000, {IVANNA: 60000, NASTIA: 30000, MARYNA: 50000})


def test_exact_rejects_sum_above_amount():
    with pytest.raises(ValueError, match="перевищено"):
        split_exact(1000, {IVANNA: 800, NASTIA: 300})


def test_exact_rejects_negative_share():
    with pytest.raises(ValueError):
        split_exact(1000, {IVANNA: 1500, NASTIA: -500})


def test_exact_rejects_all_zero():
    with pytest.raises(ValueError):
        split_exact(1000, {IVANNA: 0})


# ---------- Поділ чека за позиціями ----------
RESTAURANT = [
    (32000, [IVANNA]),  # Бограч
    (19000, [IVANNA]),  # Деруни
    (16000, [NASTIA]),  # Вареники
    (5000, [NASTIA]),  # Чай
    (28000, [MARYNA]),  # Банош
    (13000, [MARYNA]),  # Пляцок
    (10000, [MARYNA]),  # Глінтвейн
    (27000, [IVANNA, NASTIA, MARYNA]),  # Сирна тарілка на трьох
]


def test_items_restaurant_gives_600_300_600():
    assert split_by_items(RESTAURANT) == {IVANNA: 60000, MARYNA: 60000, NASTIA: 30000}


def test_items_total_equals_receipt_total():
    assert sum(split_by_items(RESTAURANT).values()) == sum(p for p, _ in RESTAURANT)


def test_items_shared_item_keeps_every_kopeck():
    assert split_by_items([(10000, [3, 1, 2])]) == {1: 3334, 2: 3333, 3: 3333}


def test_items_unclaimed_item_blocks_finalize():
    with pytest.raises(ValueError, match="Не всі позиції"):
        split_by_items([(1000, [IVANNA]), (500, [])])


def test_items_empty_receipt_rejected():
    with pytest.raises(ValueError):
        split_by_items([])


def test_preview_reports_unclaimed_sum():
    totals, unclaimed = preview_split([(1000, [IVANNA]), (500, []), (300, [])])
    assert totals == {IVANNA: 1000}
    assert unclaimed == 800
