"""Unit tests for app.core.security 密码哈希与 JWT."""
from datetime import datetime, timezone, timedelta

import jwt as pyjwt
import pytest

from app.config import settings
from app.core import security


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        h = security.hash_password("secret123")
        assert h != "secret123"
        assert isinstance(h, str)

    def test_hash_is_salted_unique(self):
        assert security.hash_password("secret") != security.hash_password("secret")

    def test_verify_correct_password(self):
        h = security.hash_password("correct horse")
        assert security.verify_password("correct horse", h) is True

    def test_verify_wrong_password(self):
        h = security.hash_password("correct horse")
        assert security.verify_password("wrong", h) is False

    def test_verify_invalid_hash_returns_false(self):
        assert security.verify_password("x", "not-a-bcrypt-hash") is False

    def test_verify_empty_hash_returns_false(self):
        assert security.verify_password("x", "") is False


class TestAccessToken:
    def test_roundtrip_contains_claims(self):
        token = security.create_access_token("42", "alice", "teacher")
        payload = security.decode_access_token(token)
        assert payload["sub"] == "42"
        assert payload["username"] == "alice"
        assert payload["role"] == "teacher"
        assert "exp" in payload

    def test_expiry_is_in_the_future(self):
        token = security.create_access_token("1", "bob", "student")
        payload = security.decode_access_token(token)
        assert payload["exp"] > datetime.now(timezone.utc).timestamp()

    def test_decode_rejects_tampered_token(self):
        token = security.create_access_token("1", "bob", "student")
        with pytest.raises(pyjwt.InvalidTokenError):
            security.decode_access_token(token + "tampered")

    def test_decode_rejects_wrong_secret(self):
        bad = pyjwt.encode(
            {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            "the-wrong-secret",
            algorithm="HS256",
        )
        with pytest.raises(pyjwt.InvalidSignatureError):
            security.decode_access_token(bad)

    def test_decode_rejects_expired_token(self):
        expired = pyjwt.encode(
            {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
            settings.JWT_SECRET,
            algorithm="HS256",
        )
        with pytest.raises(pyjwt.ExpiredSignatureError):
            security.decode_access_token(expired)
