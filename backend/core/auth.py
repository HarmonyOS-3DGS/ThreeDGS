"""JWT-based authentication — ServiceAccount pattern (OAuth2 Client Credentials)."""

import logging

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer

from backend.core.config import settings

logger = logging.getLogger(__name__)

BEARER_SCHEME = HTTPBearer(auto_error=False)


def _auth_enabled() -> bool:
    return bool(settings.service_accounts_raw)


def _decode_jwt(token: str) -> dict:
    key = settings.jwt_secret_key
    if not key:
        raise HTTPException(
            status_code=500,
            detail="JWT_SECRET_KEY not configured",
        )
    try:
        payload = jwt.decode(token, key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")


def get_current_client_id(token_data: dict = Security(BEARER_SCHEME)) -> tuple[str, str]:
    """返回 (client_id, raw_token)。raw_token 用于回退 URL 等场景。"""
    if not _auth_enabled():
        return "", ""
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    payload = _decode_jwt(token_data.credentials)
    return payload.get("client_id", ""), token_data.credentials


def get_admin_client_id() -> str:
    return settings.admin_client_id
