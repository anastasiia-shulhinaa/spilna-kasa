from app.services.invites import ALPHABET, CODE_LENGTH, generate_code, normalize_code, unique_code


def test_code_has_expected_length_and_alphabet():
    code = generate_code()
    assert len(code) == CODE_LENGTH
    assert set(code) <= set(ALPHABET)


def test_alphabet_has_no_confusable_characters():
    assert not set("0O1IL") & set(ALPHABET)


def test_unique_code_skips_existing_codes():
    taken = {generate_code() for _ in range(5)}
    code = unique_code(lambda c: c in taken)
    assert code not in taken


def test_normalize_code_ignores_case_spaces_and_dashes():
    assert normalize_code(" kas-a 26 ") == "KASA26"
