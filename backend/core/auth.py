"""Authorization header authentication."""
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from backend.core.config import settings

AUTH_HEADER = APIKeyHeader(name="Authorization", auto_error=False)


def _verify_auth_key(auth_header: str | None) -> str:
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ret": {"code": 401, "msg": "Missing Authorization header"}},
        )
    expected = getattr(settings, "api_key", None)
    if not expected:
        return auth_header
    if auth_header != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ret": {"code": 401, "msg": "Invalid Authorization"}},
        )
    return auth_header


def verify_app_auth(auth_header: str = Security(AUTH_HEADER)) -> str:
    """应用级鉴权 - 用于创建任务."""
    return _verify_auth_key(auth_header)


def verify_project_auth(auth_header: str = Security(AUTH_HEADER)) -> str:
    """项目级鉴权 - 用于启动、查询、SSE."""
    return _verify_auth_key(auth_header)
