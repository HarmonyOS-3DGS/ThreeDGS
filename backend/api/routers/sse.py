"""Server-Sent Events for real-time project progress."""
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from sse_starlette.sse import EventSourceResponse

from backend.core.database import Project
from backend.api.deps import get_database
from backend.core.auth import verify_api_key

router = APIRouter(prefix="/projects", tags=["sse"], dependencies=[Depends(verify_api_key)])


async def project_event_generator(project_id: str, db: Session):
    """Generate SSE events for project status updates."""
    while True:
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
        except Exception:
            # Fallback for SQLite where UUID comparison may differ
            project = db.query(Project).filter(Project.id == str(project_id)).first()

        if not project:
            yield {
                "event": "error",
                "data": json.dumps({"detail": "Project not found"}),
            }
            break

        data = {
            "status": project.status,
            "stage": project.current_stage,
            "progress": project.progress,
            "updated_at": project.updated_at.isoformat() if project.updated_at else "",
        }
        yield {"event": "status", "data": json.dumps(data)}

        if project.status in ("completed", "failed"):
            yield {"event": "done", "data": json.dumps({"final_status": project.status})}
            break

        await asyncio.sleep(2)


@router.get("/{project_id}/events")
async def project_events(project_id: UUID, db: Session = Depends(get_database)):
    """SSE endpoint for real-time project progress."""
    project = db.query(Project).filter(Project.id == str(project_id)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return EventSourceResponse(
        project_event_generator(str(project_id), db),
    )
