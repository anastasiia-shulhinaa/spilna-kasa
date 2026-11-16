import pytest

from app.services.money import format_kop, parse_amount, split_equal


def test_split_even_amount():
    assert split_equal(60000, [1, 2, 3]) == {1: 20000, 2: 20000, 3: 20000}


def test_split_100_by_3_keeps_every_kopeck():
    shares = split_equal(10000, [1, 2, 3])
    assert shares == {1: 3334, 2: 3333, 3: 3333}
    assert sum(shares.values()) == 10000


def test_split_single_participant_gets_everything():
    assert split_equal(12345, [7]) == {7: 12345}


def test_split_remainder_goes_to_lowest_ids_regardless_of_input_order():
    assert split_equal(101, [9, 3, 5]) == {3: 34, 5: 34, 9: 33}


@pytest.mark.parametrize("amount", [1, 2, 99, 1000, 99999, 1234567])
def test_split_sum_always_equals_amount_for_seven_people(amount):
    shares = split_equal(amount, list(range(1, 8)))
    assert sum(shares.values()) == amount
    assert max(shares.values()) - min(shares.values()) <= 1


def test_split_rejects_zero_amount():
    with pytest.raises(ValueError):
        split_equal(0, [1, 2])


def test_split_rejects_negative_amount():
    with pytest.raises(ValueError):
        split_equal(-500, [1, 2])


def test_split_rejects_empty_participants():
    with pytest.raises(ValueError):
        split_equal(1000, [])


def test_split_rejects_duplicate_participants():
    with pytest.raises(ValueError):
        split_equal(1000, [1, 1, 2])


@pytest.mark.parametrize(
    ("text", "kop"),
    [("600", 60000), ("33,34", 3334), ("0.5", 50), ("1 250,00", 125000), (" 99,9 ", 9990)],
)
def test_parse_amount_valid(text, kop):
    assert parse_amount(text) == kop


@pytest.mark.parametrize("text", ["", "abc", "-200", "12,345", "0", "0,00", "1e5"])
def test_parse_amount_invalid(text):
    with pytest.raises(ValueError):
        parse_amount(text)


def test_format_kop():
    assert format_kop(123456) == "1 234,56 ₴"
    assert format_kop(-20000) == "−200,00 ₴"
    assert format_kop(5) == "0,05 ₴"
