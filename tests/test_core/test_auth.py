"""Tests for JWT auth module."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from backend.core.auth import _decode_jwt
from backend.core.config import settings


class TestJWTAuth:
    def test_decode_valid_token(self):
        token = jwt.encode(
            {"client_id": "test-client", "exp": datetime.now(UTC) + timedelta(hours=1)},
            "test-jwt-secret",
            algorithm="HS256",
        )
        payload = _decode_jwt(token)
        assert payload["client_id"] == "test-client"

    def test_expired_token_raises_401(self):
        token = jwt.encode(
            {"client_id": "test-client", "exp": datetime.now(UTC) - timedelta(hours=1)},
            "test-jwt-secret",
            algorithm="HS256",
        )
        with pytest.raises(HTTPException) as exc:
            _decode_jwt(token)
        assert exc.value.status_code == 401

    def test_invalid_signature_raises_401(self):
        token = jwt.encode(
            {"client_id": "test-client", "exp": datetime.now(UTC) + timedelta(hours=1)},
            "wrong-secret",
            algorithm="HS256",
        )
        with pytest.raises(HTTPException) as exc:
            _decode_jwt(token)
        assert exc.value.status_code == 401

    def test_empty_key_raises_500(self, monkeypatch):
        monkeypatch.setattr(settings, "jwt_secret_key", "")
        with pytest.raises(HTTPException) as exc:
            _decode_jwt("anything")
        assert exc.value.status_code == 500
