"""Deprecated - use /tasks endpoints instead."""
from fastapi import APIRouter, HTTPException, Depends
from backend.core.auth import verify_api_key

router = APIRouter(prefix="/projects", tags=["deprecated"], dependencies=[Depends(verify_api_key)])


@router.get("", deprecated=True)
def list_projects_deprecated():
    """DEPRECATED: Use GET /tasks instead."""
    raise HTTPException(status_code=410, detail="此接口已废弃，请使用 GET /tasks")


@router.get("/{project_id}", deprecated=True)
def get_project_deprecated():
    """DEPRECATED: Use GET /tasks/{task_id} instead."""
    raise HTTPException(status_code=410, detail="此接口已废弃，请使用 GET /tasks/{task_id}")
