"""Server-Sent Events for real-time task progress."""
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from sse_starlette.sse import EventSourceResponse

from backend.core.database import Task
from backend.api.deps import get_database
from backend.core.auth import verify_api_key

router = APIRouter(prefix="/tasks", tags=["sse"], dependencies=[Depends(verify_api_key)])


async def task_event_generator(task_id: str, db: Session):
    """Generate SSE events for task status updates."""
    while True:
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
        except Exception:
            task = db.query(Task).filter(Task.id == str(task_id)).first()

        if not task:
            yield {
                "event": "error",
                "data": json.dumps({"detail": "Task not found"}),
            }
            break

        data = {
            "status": task.status,
            "stage": task.current_stage,
            "progress": task.progress,
            "remaining_time": task.remaining_time,
            "updated_at": task.updated_at.isoformat() if task.updated_at else "",
        }
        yield {"event": "status", "data": json.dumps(data)}

        if task.status in ("completed", "failed"):
            yield {"event": "done", "data": json.dumps({"final_status": task.status})}
            break

        await asyncio.sleep(2)


@router.get("/{task_id}/events")
async def task_events(task_id: UUID, db: Session = Depends(get_database)):
    """SSE endpoint for real-time task progress."""
    task = db.query(Task).filter(Task.id == str(task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return EventSourceResponse(
        task_event_generator(str(task_id), db),
    )
