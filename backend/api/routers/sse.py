"""Server-Sent Events for real-time task progress."""
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from backend.core.database import Task
from backend.api.deps import get_database
from backend.core.config import settings

router = APIRouter(prefix="/tasks", tags=["sse"])


def _verify_sse_auth(
    projectId_h: str | None = Header(None, alias="projectId"),
    projectId_q: str | None = Query(None, alias="projectId"),
    auth_h: str | None = Header(None, alias="Authorization"),
    auth_q: str | None = Query(None, alias="Authorization"),
):
    pid = projectId_h or projectId_q
    token = auth_h or auth_q
    if not token:
        raise HTTPException(status_code=401, detail={"ret": {"code": 401, "msg": "Missing Authorization"}})
    expected = getattr(settings, "api_key", None)
    if expected and token != expected:
        raise HTTPException(status_code=401, detail={"ret": {"code": 401, "msg": "Invalid Authorization"}})
    if not pid:
        raise HTTPException(status_code=422, detail={"ret": {"code": 422, "msg": "Missing projectId"}})
    return pid


async def task_event_generator(task_id: str, project_id: str, db: Session):
    while True:
        try:
            task = db.query(Task).filter(
                Task.id == task_id, Task.project_id == project_id
            ).first()
        except Exception:
            task = db.query(Task).filter(
                Task.id == str(task_id), Task.project_id == project_id
            ).first()

        if not task:
            yield {"event": "error", "data": json.dumps({"detail": "Task not found"})}
            break

        data = {
            "status": task.status,
            "stage": task.current_stage,
            "progress": task.progress,
            "remainingTime": task.remaining_time,
            "updatedAt": task.updated_at.isoformat() if task.updated_at else "",
        }
        yield {"event": "status", "data": json.dumps(data)}

        if task.status in ("completed", "failed"):
            yield {"event": "done", "data": json.dumps({"finalStatus": task.status})}
            break

        await asyncio.sleep(2)


@router.get("/{task_id}/events")
async def task_events(
    task_id: str,
    pid: str = Depends(_verify_sse_auth),
    db: Session = Depends(get_database),
):
    task = db.query(Task).filter(
        Task.id == task_id, Task.project_id == pid
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})

    return EventSourceResponse(task_event_generator(task_id, pid, db))
