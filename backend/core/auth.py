"""Simple API Key authentication for internal use."""
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from backend.core.config import settings

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify the API key from request header."""
    expected = getattr(settings, "api_key", None)
    if not expected:
        # No key configured = open access
        return api_key or ""

    if api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": API_KEY_NAME},
        )
    return api_key
