"""Token 颁发端点 — OAuth2 Client Credentials 风格。"""

import logging
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Header, HTTPException

from backend.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/token")
def get_token(
    authorization: str = Header(..., alias="Authorization"),
):
    if not authorization.startswith("Basic "):
        raise HTTPException(status_code=401, detail="must use Basic auth")

    import base64

    try:
        decoded = base64.b64decode(authorization[len("Basic ") :]).decode("utf-8")
        client_id, secret = decoded.split(":", 1)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid Basic auth format")

    accounts = settings.service_accounts
    sign_key = settings.jwt_secret_key
    if not accounts:
        client_id = "dev"
        if not sign_key:
            sign_key = "dev-only-do-not-use-in-production"
    elif not sign_key:
        raise HTTPException(
            status_code=500,
            detail="JWT_SECRET_KEY not configured",
        )
    elif client_id not in accounts or accounts[client_id] != secret:
        raise HTTPException(status_code=401, detail="invalid client_id or secret")

    exp = datetime.now(UTC) + timedelta(seconds=settings.jwt_expire_seconds)
    payload = {"client_id": client_id, "exp": exp}
    token = jwt.encode(payload, sign_key, algorithm="HS256")

    logger.info("token issued: client_id=%s exp=%s", client_id, exp.isoformat())
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_seconds,
    }
