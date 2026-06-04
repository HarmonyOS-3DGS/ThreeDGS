"""Deprecated - use POST /tasks instead."""
from fastapi import APIRouter, HTTPException, Depends
from backend.core.auth import verify_api_key

router = APIRouter(prefix="/upload", tags=["deprecated"], dependencies=[Depends(verify_api_key)])


@router.post("", deprecated=True)
def upload_file_deprecated():
    """DEPRECATED: Use POST /tasks instead."""
    raise HTTPException(status_code=410, detail="此接口已废弃，请使用 POST /tasks")
