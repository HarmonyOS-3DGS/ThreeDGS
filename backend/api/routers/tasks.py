"""Task management routes: create, list, start, query."""
import hashlib
import json
import os
import shutil
from datetime import datetime

import aiofiles.os
import aiofiles
from aiofiles import os as aio_os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.core.database import Task, TaskFile, TaskStatus, TaskStage
from backend.api.schemas.task import (
    CreateTaskReq, CreateTaskRsp, FileInfo, GetTaskRsp,
    StartTaskRsp, TaskListResponse, VALID_FILE_ROLES,
)
from backend.api.deps import get_database
from backend.core.auth import verify_app_auth, verify_project_auth
from backend.core.config import TASK_OUTPUT_DIR
from backend.core.task_publisher import submit_pipeline
from backend.core.storage import storage
from backend.core.file_utils import detect_mime

router = APIRouter(prefix="/tasks", tags=["taskManagement"])


def _safe_filename(filename: str) -> str:
    """Sanitize filename, prevent path traversal."""
    return os.path.basename(filename)


async def _save_file(task_id: str, fi: FileInfo, content: bytes = b"", file_role: str = "source_video") -> FileInfo:
    safe_name = _safe_filename(fi.fileName)
    task_dir = os.path.join(TASK_OUTPUT_DIR, str(task_id))
    await aiofiles.os.makedirs(task_dir, exist_ok=True)

    local_path = os.path.join(task_dir, safe_name)
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
        detected_mime = detect_mime(content)
        # 魔数校验: source_video 必须是视频, source_images 必须是图片
        if detected_mime:
            if file_role == "source_video" and not detected_mime.startswith("video/"):
                raise HTTPException(status_code=400, detail={
                    "ret": {"code": 400, "msg": f"文件 {safe_name} 声明为视频，但实际类型为 {detected_mime}"}})
            if file_role == "source_images" and not detected_mime.startswith("image/"):
                raise HTTPException(status_code=400, detail={
                    "ret": {"code": 400, "msg": f"文件 {safe_name} 声明为图片，但实际类型为 {detected_mime}"}})
        async with aiofiles.open(local_path, "wb") as f:
            await f.write(content)

    # 上传到对象存储（MinIO 或本地 fallback）
    object_name = f"tasks/{task_id}/{safe_name}"
    try:
        storage.upload_file(object_name, local_path)
        file_url = object_name
    except Exception:
        file_url = local_path

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
            errorMessage=t.error_message or "",
            downloadInfos=[],
        )
        for t in tasks
    ]
    return TaskListResponse(items=items, total=len(items))


def _validate_body(ec: str, sc: str, file_infos: list[FileInfo]) -> CreateTaskReq:
    """Pydantic 校验并返回标准化 body。"""
    try:
        return CreateTaskReq(externalCode=ec, scene=sc, fileInfos=file_infos)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail={"ret": {"code": 422, "msg": str(e)}})


async def _parse_request_body(request: Request) -> tuple[str, str, list[FileInfo], dict[str, bytes]]:
    """解析 JSON 或 multipart 请求体，返回 (externalCode, scene, fileInfos, file_contents)。"""
    content_type = request.headers.get("content-type", "")
    file_contents: dict[str, bytes] = {}

    if "application/json" in content_type:
        data = await request.json()
        body = _validate_body(
            data.get("externalCode", ""),
            data.get("scene", ""),
            [FileInfo(**m) for m in data.get("fileInfos", [])],
        )
        return body.externalCode, body.scene, body.fileInfos, file_contents

    if "multipart/form-data" in content_type:
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
        body = _validate_body(ec, sc, file_infos)
        return body.externalCode, body.scene, body.fileInfos, file_contents

    raise HTTPException(status_code=400,
        detail={"ret": {"code": 400, "msg": "Unsupported content-type, use application/json or multipart/form-data"}})


async def _save_task_files(db: Session, task_id: str, file_infos: list[FileInfo],
                           file_contents: dict[str, bytes]) -> list[FileInfo]:
    """保存上传文件并写入 TaskFile 记录，返回保存后的 FileInfo 列表。"""
    result_files = []
    for fi in file_infos:
        role = fi.fileRole if fi.fileRole in VALID_FILE_ROLES else "source_video"
        content = file_contents.get(fi.fileName, b"")
        saved = await _save_file(task_id, fi, content=content, file_role=role)
        task_file = TaskFile(
            task_id=task_id,
            fileName=saved.fileName,
            sha256=saved.sha256,
            contentLength=saved.contentLength,
            fileUrl=saved.fileUrl,
            fileRole=role,
            mimeType=fi.mimeType,
        )
        db.add(task_file)
        result_files.append(saved)
    db.commit()
    return result_files


@router.post("", response_model=CreateTaskRsp)
async def create_task(
    request: Request,
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    _auth: str = Depends(verify_app_auth),
):
    """创建3DGS任务。支持 JSON body 或 multipart/form-data."""
    ec, sc, file_infos, file_contents = await _parse_request_body(request)

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

    result_files = await _save_task_files(db, task.id, file_infos, file_contents)
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
        # 确保流水线需要的视频文件在共享卷上可用
        remote_path = first_video.fileUrl
        local_video = os.path.join(TASK_OUTPUT_DIR, str(task_id), os.path.basename(remote_path))
        if not os.path.exists(local_video):
            try:
                storage.download_file(remote_path, local_video)
            except Exception:
                pass
        submit_pipeline(task_id, local_video)
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
    output_files = db.query(TaskFile).filter(
        TaskFile.task_id == task.id,
        TaskFile.fileRole == "compressed_model",
    ).all()
    for f in output_files:
        download_infos.append(FileInfo(
            fileName=f.fileName,
            sha256=f.sha256,
            contentLength=f.contentLength,
            fileUrl=f.fileUrl,
            fileRole=f.fileRole,
            mimeType=f.mimeType,
        ))

    return GetTaskRsp(
        taskId=task.id,
        status=task.status,
        currentStage=task.current_stage,
        progress=task.progress,
        remainingTime=task.remaining_time,
        scene=task.scene,
        errorMessage=task.error_message or "",
        downloadInfos=download_infos,
    )


@router.get("/{task_id}/download")
def download_file(
    task_id: str,
    file: str,
    projectId_h: str | None = Header(None, alias="projectId", max_length=20),
    projectId_q: str | None = Query(None, alias="projectId", max_length=20),
    auth_h: str | None = Header(None, alias="Authorization"),
    auth_q: str | None = Query(None, alias="Authorization"),
    db: Session = Depends(get_database),
):
    """下载任务输出文件."""
    from backend.core.auth import _verify_auth_key
    _verify_auth_key(auth_h or auth_q)
    pid = projectId_h or projectId_q
    if not pid:
        raise HTTPException(status_code=422, detail={"ret": {"code": 422, "msg": "Missing projectId"}})

    task = db.query(Task).filter(Task.id == task_id, Task.project_id == pid).first()
    if not task:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})

    safe_name = _safe_filename(file)
    # 从 DB 查找 compressed_model 记录
    task_file = db.query(TaskFile).filter(
        TaskFile.task_id == task_id,
        TaskFile.fileRole == "compressed_model",
        TaskFile.fileName == safe_name,
    ).first()
    if task_file:
        try:
            url = storage.get_presigned_url(task_file.fileUrl, expires=3600)
            return RedirectResponse(url=url)
        except Exception:
            pass

    # 回退到本地文件
    fpath = os.path.join(TASK_OUTPUT_DIR, str(task.id), "compressed", safe_name)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "File not found"}})

    return FileResponse(fpath, filename=safe_name)
