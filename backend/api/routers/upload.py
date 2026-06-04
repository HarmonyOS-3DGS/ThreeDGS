"""File upload and pipeline submission routes."""
import os
import shutil
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from backend.core.database import Project, ProjectStatus
from backend.api.schemas.project import ProjectResponse
from backend.api.deps import get_database
from backend.core.auth import verify_api_key
from backend.worker.tasks.pipeline import submit_training_pipeline

router = APIRouter(prefix="/upload", tags=["upload"], dependencies=[Depends(verify_api_key)])

UPLOAD_DIR = "/tmp/3dgs-uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("", response_model=ProjectResponse)
def upload_file(
    name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_database),
):
    """Upload a video/image file and start the training pipeline."""
    project = Project(name=name, status=ProjectStatus.PENDING.value)
    db.add(project)
    db.commit()
    db.refresh(project)

    # Save uploaded file locally
    ext = os.path.splitext(file.filename or "")[1]
    local_path = os.path.join(UPLOAD_DIR, f"{project.id}{ext}")
    with open(local_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    project.raw_upload_path = local_path
    db.commit()

    # Submit Celery pipeline
    submit_training_pipeline(str(project.id), local_path)

    return ProjectResponse.model_validate(project)
