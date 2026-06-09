"""Server-Sent Events for real-time task progress."""
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sse_starlette.sse import EventSourceResponse

from backend.core.database import SessionLocal, Task
from backend.core.auth import _verify_auth_key

router = APIRouter(prefix="/tasks", tags=["sse"])


def _verify_sse_auth(
    projectId_h: str | None = Header(None, alias="projectId"),
    projectId_q: str | None = Query(None, alias="projectId"),
    auth_h: str | None = Header(None, alias="Authorization"),
    auth_q: str | None = Query(None, alias="Authorization"),
):
    token = auth_h or auth_q
    _verify_auth_key(token)
    pid = projectId_h or projectId_q
    if not pid:
        raise HTTPException(status_code=422, detail={"ret": {"code": 422, "msg": "Missing projectId"}})
    return pid


def _fetch_task_status(task_id: str, project_id: str) -> dict | None:
    """同步查询任务状态，在 thread pool 中执行，不阻塞事件循环。"""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(
            Task.id == task_id, Task.project_id == project_id
        ).first()
        if not task:
            return None
        return {
            "status": task.status,
            "stage": task.current_stage,
            "progress": task.progress,
            "remainingTime": task.remaining_time,
            "updatedAt": task.updated_at.isoformat() if task.updated_at else "",
        }
    finally:
        db.close()


async def task_event_generator(task_id: str, project_id: str):
    while True:
        data = await asyncio.to_thread(_fetch_task_status, task_id, project_id)

        if data is None:
            yield {"event": "error", "data": json.dumps({"ret": {"code": 404, "msg": "Task not found"}})}
            break

        yield {"event": "status", "data": json.dumps(data)}

        if data["status"] in ("completed", "failed"):
            yield {"event": "done", "data": json.dumps({"finalStatus": data["status"]})}
            break

        await asyncio.sleep(2)


@router.get("/{task_id}/events")
async def task_events(
    task_id: str,
    pid: str = Depends(_verify_sse_auth),
):
    # 快速预检任务是否存在
    data = await asyncio.to_thread(_fetch_task_status, task_id, pid)
    if data is None:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})

    return EventSourceResponse(task_event_generator(task_id, pid))
