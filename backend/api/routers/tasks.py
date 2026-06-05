"""Task management routes: create, start, query."""
import hashlib
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from backend.core.database import Task, TaskFile, TaskStatus, TaskStage
from backend.api.schemas.task import (
    CreateTaskReq, CreateTaskRsp, StartTaskRsp, GetTaskRsp,
    FileInfo, ConnectRet,
)
from backend.api.deps import get_database
from backend.core.auth import verify_app_auth, verify_project_auth
from backend.core.config import settings
from backend.worker.tasks.pipeline import submit_training_pipeline

router = APIRouter(prefix="/tasks", tags=["taskManagement"])

UPLOAD_DIR = os.path.join(settings.local_storage_dir, "uploads")


@router.post("", response_model=CreateTaskRsp)
def create_task(
    body: CreateTaskReq,
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    _auth: str = Depends(verify_app_auth),
):
    """创建3DGS任务，状态为 pending."""
    task = Task(
        project_id=projectId,
        external_code=body.externalCode,
        scene=body.scene,
        status=TaskStatus.PENDING.value,
        current_stage=TaskStage.INITIALIZING.value,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    task_dir = os.path.join(UPLOAD_DIR, str(task.id))
    os.makedirs(task_dir, exist_ok=True)

    file_infos = []
    for fi in body.fileInfos:
        file_url = os.path.join(task_dir, fi.fileName)
        content = b""
        if os.path.exists(fi.fileUrl):
            with open(fi.fileUrl, "rb") as f:
                content = f.read()

        actual_sha256 = fi.sha256 or ""
        if content:
            actual_sha256 = hashlib.sha256(content).hexdigest()
            with open(file_url, "wb") as f:
                f.write(content)

        content_length = fi.contentLength or len(content)

        task_file = TaskFile(
            task_id=task.id,
            fileName=fi.fileName,
            sha256=actual_sha256,
            contentLength=content_length,
            fileUrl=file_url,
        )
        db.add(task_file)
        file_infos.append(FileInfo(
            fileName=fi.fileName,
            sha256=actual_sha256,
            contentLength=content_length,
            fileUrl=file_url,
        ))

    db.commit()

    return CreateTaskRsp(taskId=task.id, fileInfos=file_infos)


@router.post("/{task_id}/start", response_model=StartTaskRsp)
def start_task(
    task_id: str,
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    _auth: str = Depends(verify_project_auth),
):
    """启动任务（pending → processing）."""
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == projectId).first()
    if not task:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})

    if task.status != TaskStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail={"ret": {"code": 400, "msg": f"Task status is {task.status}, expected pending"}},
        )

    task.status = TaskStatus.PROCESSING.value
    task.current_stage = TaskStage.INITIALIZING.value
    task.progress = 0
    task.remaining_time = 15
    db.commit()

    task_files = db.query(TaskFile).filter(TaskFile.task_id == task_id).all()
    first_video = next(
        (f for f in task_files if f.fileName.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))),
        task_files[0] if task_files else None,
    )

    if first_video:
        submit_training_pipeline(task_id, first_video.fileUrl)
    else:
        task.status = TaskStatus.FAILED.value
        task.error_message = "没有找到可处理的视频文件"
        db.commit()
        raise HTTPException(status_code=400, detail={"ret": {"code": 400, "msg": "没有找到可处理的视频文件"}})

    return StartTaskRsp(remainingTime=15)


@router.get("/{task_id}", response_model=GetTaskRsp)
def query_task(
    task_id: str,
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    _auth: str = Depends(verify_project_auth),
):
    """查询任务状态及输出文件."""
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == projectId).first()
    if not task:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})

    download_infos = []
    if task.status == TaskStatus.COMPLETED.value:
        compressed_dir = os.path.join(UPLOAD_DIR, str(task.id), "compressed")
        if os.path.isdir(compressed_dir):
            for fname in os.listdir(compressed_dir):
                fpath = os.path.join(compressed_dir, fname)
                if os.path.isfile(fpath):
                    download_infos.append(FileInfo(
                        fileName=fname,
                        sha256="",
                        contentLength=os.path.getsize(fpath),
                        fileUrl=fpath,
                    ))

    return GetTaskRsp(
        status=task.status,
        currentStage=task.current_stage,
        progress=task.progress,
        remainingTime=task.remaining_time,
        downloadInfos=download_infos,
    )
