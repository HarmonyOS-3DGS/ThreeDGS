"""Task management routes: create, list, start, query."""
import hashlib
import json
import os
import shutil
from datetime import datetime

import aiofiles.os
import aiofiles
from aiofiles import os as aio_os

from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.core.database import Task, TaskFile, TaskStatus, TaskStage
from backend.api.schemas.task import (
    CreateTaskReq, CreateTaskRsp, FileInfo, GetTaskRsp,
    StartTaskRsp, TaskListResponse,
)
from backend.api.deps import get_database
from backend.core.auth import verify_app_auth, verify_project_auth
from backend.core.config import TASK_OUTPUT_DIR
from backend.core.task_publisher import submit_pipeline

router = APIRouter(prefix="/tasks", tags=["taskManagement"])


def _safe_filename(filename: str) -> str:
    """Sanitize filename, prevent path traversal."""
    return os.path.basename(filename)


async def _save_file(task_id: str, fi: FileInfo, content: bytes = b"") -> FileInfo:
    safe_name = _safe_filename(fi.fileName)
    task_dir = os.path.join(TASK_OUTPUT_DIR, str(task_id))
    await aiofiles.os.makedirs(task_dir, exist_ok=True)

    file_url = os.path.join(task_dir, safe_name)
    actual_sha256 = fi.sha256 or ""
    content_length = fi.contentLength or 0

    if not content and fi.fileUrl:
        safe_url = os.path.join(task_dir, _safe_filename(os.path.basename(fi.fileUrl)))
        if os.path.isfile(safe_url):
            async with aiofiles.open(safe_url, "rb") as f:
                content = await f.read()

    if content:
        actual_sha256 = hashlib.sha256(content).hexdigest()
        content_length = len(content)
        async with aiofiles.open(file_url, "wb") as f:
            await f.write(content)

    return FileInfo(
        fileName=safe_name,
        sha256=actual_sha256,
        contentLength=content_length,
        fileUrl=file_url,
    )


@router.get("", response_model=TaskListResponse)
def list_tasks(
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    _auth: str = Depends(verify_project_auth),
):
    """列出指定项目的所有任务."""
    tasks = (
        db.query(Task)
        .filter(Task.project_id == projectId)
        .order_by(Task.created_at.desc())
        .all()
    )
    items = [
        GetTaskRsp(
            taskId=t.id,
            status=t.status,
            currentStage=t.current_stage,
            progress=t.progress,
            remainingTime=t.remaining_time,
            scene=t.scene,
            downloadInfos=[],
        )
        for t in tasks
    ]
    return TaskListResponse(items=items, total=len(items))


@router.post("", response_model=CreateTaskRsp)
async def create_task(
    request: Request,
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    _auth: str = Depends(verify_app_auth),
):
    """创建3DGS任务。支持 JSON body 或 multipart/form-data."""
    content_type = request.headers.get("content-type", "")

    file_contents: dict[str, bytes] = {}

    if "application/json" in content_type:
        data = await request.json()
        try:
            body = CreateTaskReq(**data)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail={"ret": {"code": 422, "msg": str(e)}})
        ec = body.externalCode
        sc = body.scene
        file_infos = body.fileInfos
    elif "multipart/form-data" in content_type:
        form = await request.form()
        ec = form.get("externalCode") or ""
        sc = form.get("scene") or ""
        fm = form.get("filesMeta") or "[]"
        if isinstance(fm, str):
            file_infos = [FileInfo(**m) for m in json.loads(fm)]
        else:
            file_infos = [FileInfo(**m) for m in json.loads(str(fm))]
        upload_files = form.getlist("files")
        for f in upload_files:
            if hasattr(f, "filename") and f.filename:
                file_contents[f.filename] = await f.read()
        for fi in file_infos:
            content = file_contents.get(fi.fileName, b"")
            if content:
                fi.sha256 = hashlib.sha256(content).hexdigest()
                fi.contentLength = len(content)
    else:
        raise HTTPException(status_code=400,
            detail={"ret": {"code": 400, "msg": "Unsupported content-type, use application/json or multipart/form-data"}})

    if not ec or not sc or not file_infos:
        raise HTTPException(status_code=400, detail={"ret": {"code": 400, "msg": "缺少必要参数"}})

    task = Task(
        project_id=projectId,
        external_code=ec,
        scene=sc,
        status=TaskStatus.PENDING.value,
        current_stage=TaskStage.INITIALIZING.value,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    result_files = []
    for fi in file_infos:
        content = file_contents.get(fi.fileName, b"")
        saved = await _save_file(task.id, fi, content=content)
        task_file = TaskFile(
            task_id=task.id,
            fileName=saved.fileName,
            sha256=saved.sha256,
            contentLength=saved.contentLength,
            fileUrl=saved.fileUrl,
        )
        db.add(task_file)
        result_files.append(saved)

    db.commit()

    return CreateTaskRsp(taskId=task.id, fileInfos=result_files)


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
        submit_pipeline(task_id, first_video.fileUrl)
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
        compressed_dir = os.path.join(TASK_OUTPUT_DIR, str(task.id), "compressed")
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
        taskId=task.id,
        status=task.status,
        currentStage=task.current_stage,
        progress=task.progress,
        remainingTime=task.remaining_time,
        scene=task.scene,
        downloadInfos=download_infos,
    )


@router.get("/{task_id}/download")
def download_file(
    task_id: str,
    file: str,
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    _auth: str = Depends(verify_project_auth),
):
    """下载任务输出文件."""
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == projectId).first()
    if not task:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})

    safe_name = _safe_filename(file)
    fpath = os.path.join(TASK_OUTPUT_DIR, str(task.id), "compressed", safe_name)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "File not found"}})

    return FileResponse(fpath, filename=safe_name)
