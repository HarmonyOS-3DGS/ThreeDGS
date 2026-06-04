"""Project status and listing routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from backend.core.database import Project
from backend.api.schemas.project import ProjectResponse, ProjectListResponse
from backend.api.deps import get_database
from backend.core.auth import verify_api_key

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=ProjectListResponse)
def list_projects(db: Session = Depends(get_database)):
    """List all projects ordered by creation time (newest first)."""
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=len(projects),
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: UUID, db: Session = Depends(get_database)):
    """Get a single project by ID."""
    project = db.query(Project).filter(Project.id == str(project_id)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(project)
