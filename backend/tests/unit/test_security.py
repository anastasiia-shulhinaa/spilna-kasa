import jwt

from app.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_is_not_plain_text():
    h = hash_password("demo1234")
    assert h != "demo1234"
    assert verify_password("demo1234", h)


def test_wrong_password_is_rejected():
    assert not verify_password("wrong", hash_password("demo1234"))


def test_same_password_gets_different_hashes():
    assert hash_password("demo1234") != hash_password("demo1234")


def test_token_roundtrip_returns_user_id():
    assert decode_access_token(create_access_token(42)) == 42


def test_expired_token_is_rejected():
    assert decode_access_token(create_access_token(42, ttl_minutes=-1)) is None


def test_token_signed_with_foreign_secret_is_rejected():
    forged = jwt.encode({"sub": "42"}, "someone-elses-secret", algorithm="HS256")
    assert decode_access_token(forged) is None


def test_garbage_token_is_rejected():
    assert decode_access_token("not-a-jwt") is None
