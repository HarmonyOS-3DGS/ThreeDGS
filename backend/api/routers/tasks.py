"""Task management routes: create, start, query."""
import hashlib
import json
import os
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.database import Task, TaskFile, TaskStatus
from backend.api.schemas.task import FileInfo, TaskCreateResponse, TaskStartResponse, TaskQueryResponse
from backend.api.deps import get_database
from backend.core.auth import verify_api_key
from backend.core.config import settings
from backend.worker.tasks.pipeline import submit_training_pipeline

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(verify_api_key)])

UPLOAD_DIR = os.path.join(settings.local_storage_dir, "uploads")


class FileUploadMeta(BaseModel):
    """Schema for file metadata in create task request."""
    original_filename: str
    sha256: str
    file_size: int


@router.post("", response_model=TaskCreateResponse, status_code=200)
def create_task(
    external_code: str = Form(...),
    files_meta: str = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_database),
):
    """Create a task with uploaded files and metadata.

    - external_code: 外部系统唯一标识码
    - files_meta: JSON 数组，每个元素包含 original_filename、sha256、file_size
    - files: 上传的文件二进制内容（与 files_meta 按顺序一一对应）
    """
    metas = [FileUploadMeta(**m) for m in json.loads(files_meta)]

    if len(metas) != len(files):
        raise HTTPException(status_code=400, detail="files_meta 与 files 数量不一致")

    task = Task(external_code=external_code, status=TaskStatus.QUEUED.value)
    db.add(task)
    db.commit()
    db.refresh(task)

    task_dir = os.path.join(UPLOAD_DIR, str(task.id))
    os.makedirs(task_dir, exist_ok=True)

    file_infos = []
    for meta, upload_file in zip(metas, files):
        file_path = os.path.join(task_dir, meta.original_filename)
        content = upload_file.file.read()
        actual_sha256 = hashlib.sha256(content).hexdigest()

        with open(file_path, "wb") as f:
            f.write(content)

        task_file = TaskFile(
            task_id=task.id,
            original_filename=meta.original_filename,
            sha256=actual_sha256,
            file_size=len(content),
            file_path=file_path,
        )
        db.add(task_file)
        file_infos.append(FileInfo(
            original_filename=meta.original_filename,
            sha256=actual_sha256,
            file_size=len(content),
            file_path=file_path,
        ))

    db.commit()

    return TaskCreateResponse(task_id=UUID(task.id), files=file_infos)


@router.post("/{task_id}/start", response_model=TaskStartResponse)
def start_task(task_id: UUID, db: Session = Depends(get_database)):
    """Start the training pipeline for a queued task."""
    task = db.query(Task).filter(Task.id == str(task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.QUEUED.value:
        raise HTTPException(status_code=400, detail=f"Task status is {task.status}, expected queued")

    task.status = TaskStatus.PROCESSING.value
    task.current_stage = "pending"
    task.progress = 0
    task.remaining_time = 15
    db.commit()

    task_files = db.query(TaskFile).filter(TaskFile.task_id == str(task_id)).all()
    first_video = next(
        (f for f in task_files if f.original_filename.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))),
        task_files[0] if task_files else None,
    )

    if first_video:
        submit_training_pipeline(str(task_id), first_video.file_path)
    else:
        task.status = TaskStatus.FAILED.value
        task.error_message = "没有找到可处理的视频文件"
        db.commit()
        raise HTTPException(status_code=400, detail="没有找到可处理的视频文件")

    return TaskStartResponse(code=0, msg="success", remaining_time=15)


@router.get("/{task_id}", response_model=TaskQueryResponse)
def query_task(task_id: UUID, db: Session = Depends(get_database)):
    """Query task status and output file info."""
    task = db.query(Task).filter(Task.id == str(task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    output_files = []
    if task.status == TaskStatus.COMPLETED.value:
        compressed_dir = os.path.join(UPLOAD_DIR, str(task.id), "compressed")
        for fname in os.listdir(compressed_dir) if os.path.isdir(compressed_dir) else []:
            fpath = os.path.join(compressed_dir, fname)
            if os.path.isfile(fpath):
                output_files.append(FileInfo(
                    original_filename=fname,
                    sha256="",
                    file_size=os.path.getsize(fpath),
                    file_path=fpath,
                ))

    return TaskQueryResponse(
        code=0,
        status=task.status,
        current_stage=task.current_stage,
        progress=task.progress,
        remaining_time=task.remaining_time,
        output_files=output_files,
    )
