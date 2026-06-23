"""任务管理路由：创建、列表、启动、查询、下载。"""

import logging
import os
from urllib.parse import urlencode

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from backend.api.deps import get_database
from backend.api.schemas.task import (
    VALID_FILE_ROLES,
    CreateTaskReq,
    CreateTaskRsp,
    FileInfo,
    GetTaskRsp,
    StartTaskRsp,
    TaskListResponse,
    UrlInfo,
)
from backend.core.auth import _decode_jwt, get_admin_client_id, get_current_client_id
from backend.core.config import TASK_OUTPUT_DIR, settings
from backend.core.constants import SUPPORTED_VIDEO_EXTS
from backend.core.database import Task, TaskFile, TaskStage, TaskStatus
from backend.core.file_utils import detect_mime
from backend.core.repository import TaskRepository
from backend.core.storage import storage
from backend.core.task_publisher import submit_pipeline

router = APIRouter(prefix="/tasks", tags=["taskManagement"])
logger = logging.getLogger(__name__)


def _safe_filename(filename: str) -> str:
    """Sanitize filename, prevent path traversal."""
    return os.path.basename(filename)


def _gen_upload_url(task_id: str, fi: FileInfo, token: str = "") -> UrlInfo:
    """生成上传 URL：MinIO 模式返回预签名 PUT URL，本地模式返回 API 端点。"""
    safe_name = _safe_filename(fi.fileName)
    object_name = f"tasks/{task_id}/{safe_name}"
    try:
        url = storage.get_presigned_put_url(object_name, expires=3600)
        headers = {}
        logger.info("upload url: MinIO presigned PUT %s", url)
    except Exception as e:
        url = f"/tasks/{task_id}/upload/{safe_name}"
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        logger.warning("upload url: local API %s (presign failed: %s)", url, e)
    return UrlInfo(
        objectId=safe_name,
        fileName=safe_name,
        url=url,
        method="PUT",
        headers={
            **headers,
            "Content-Type": fi.mimeType or "application/octet-stream",
        },
    )


def _gen_download_url(task_id: str, tf: TaskFile, project_id: str = "", token: str = "") -> UrlInfo:
    """生成下载 URL：MinIO 模式返回预签名 GET URL，本地模式返回 API 端点。"""
    try:
        url = storage.get_presigned_url(tf.fileUrl, expires=3600)
    except Exception:
        url = f"/tasks/{task_id}/download/{tf.fileName}"
        if project_id:
            params = {"projectId": project_id}
            if token:
                params["Authorization"] = f"Bearer {token}"
            url += f"?{urlencode(params)}"
    return UrlInfo(objectId=tf.fileName, fileName=tf.fileName, url=url, method="GET")


@router.get("", response_model=TaskListResponse)
def list_tasks(
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    client_id_token: tuple = Depends(get_current_client_id),
):
    """列出指定项目的所有任务."""
    client_id, _ = client_id_token
    q = db.query(Task).filter(Task.project_id == projectId)
    admin_id = get_admin_client_id()
    if client_id and client_id != admin_id:
        q = q.filter(Task.client_id == client_id)
    tasks = q.order_by(Task.created_at.desc()).all()
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


@router.post("", response_model=CreateTaskRsp)
def create_task(
    request: CreateTaskReq,
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    client_id_token: tuple = Depends(get_current_client_id),
):
    """创建3DGS任务。仅接收 JSON 元数据，返回预签名上传 URL。"""
    client_id, token = client_id_token
    task = Task(
        project_id=projectId,
        external_code=request.externalCode,
        scene=request.scene,
        client_id=client_id,
        status=TaskStatus.PENDING.value,
        current_stage=TaskStage.INITIALIZING.value,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    upload_infos = []
    for fi in request.fileInfos:
        safe_name = _safe_filename(fi.fileName)
        url_info = _gen_upload_url(task.id, fi, token=token)
        role = fi.fileRole if fi.fileRole in VALID_FILE_ROLES else "source_video"
        # fileUrl 存完整对象路径（MinIO 操作需要），objectId 只存文件名（给客户端看）
        task_file = TaskFile(
            task_id=task.id,
            fileName=safe_name,
            sha256="",
            contentLength=0,
            fileUrl=f"tasks/{task.id}/{safe_name}",
            fileRole=role,
            mimeType=fi.mimeType,
        )
        db.add(task_file)
        upload_infos.append(url_info)

    db.commit()
    logger.info(
        "[create] task=%s fileInfos=%d uploadUrls=%d",
        task.id,
        len(request.fileInfos),
        len(upload_infos),
    )
    return CreateTaskRsp(taskId=task.id, uploadInfos=upload_infos)


@router.put("/{task_id}/upload/{object_id:path}", tags=["fileTransfer"])
async def upload_file(
    task_id: str,
    object_id: str,
    request: Request,
    db: Session = Depends(get_database),
    client_id_token: tuple = Depends(get_current_client_id),
):
    """本地模式：接收客户端 PUT 的文件，写入本地存储。"""
    client_id, _ = client_id_token
    safe_name = _safe_filename(os.path.basename(object_id))

    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        _check_ownership(task, client_id)

    task_dir = os.path.join(TASK_OUTPUT_DIR, str(task_id))
    await aiofiles.os.makedirs(task_dir, exist_ok=True)

    local_path = os.path.join(task_dir, safe_name)
    if os.path.isfile(local_path):
        raise HTTPException(
            status_code=400, detail={"ret": {"code": 400, "msg": "file already exists"}}
        )

    content = await request.body()
    logger.info("upload: task=%s file=%s size=%d", task_id, safe_name, len(content))

    # 魔数校验
    detected_mime = detect_mime(content)
    if detected_mime:
        task_file = (
            db.query(TaskFile)
            .filter(TaskFile.task_id == task_id, TaskFile.fileName == safe_name)
            .first()
        )
        if task_file:
            role = task_file.fileRole
            if role == "source_video" and not detected_mime.startswith("video/"):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "ret": {
                            "code": 400,
                            "msg": f"declared as video, actual mime: {detected_mime}",
                        }
                    },
                )
            if role == "source_images" and not detected_mime.startswith("image/"):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "ret": {
                            "code": 400,
                            "msg": f"declared as image, actual mime: {detected_mime}",
                        }
                    },
                )

    async with aiofiles.open(local_path, "wb") as f:
        await f.write(content)

    # 同步上传到对象存储
    object_name = f"tasks/{task_id}/{safe_name}"
    try:
        storage.upload_file(object_name, local_path)
        logger.info("uploaded to MinIO: %s", object_name)
    except Exception:
        logger.warning("MinIO upload failed: %s", object_name)

    return {"ret": {"code": 0, "msg": "success"}, "fileName": safe_name, "size": len(content)}


def _check_ownership(task: Task, client_id: str):
    """校验调用者是否拥有该任务。管理员豁免。"""
    if not client_id:
        return
    admin_id = get_admin_client_id()
    if admin_id and client_id == admin_id:
        return
    if task.client_id != client_id:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})


def _estimate_remaining(task: Task, db: Session, es: int) -> int:
    return TaskRepository.estimate_queue_wait(db, task, es)


@router.post("/{task_id}/start", response_model=StartTaskRsp)
def start_task(
    task_id: str,
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    client_id_token: tuple = Depends(get_current_client_id),
):
    """启动任务（pending → processing）."""
    client_id, _ = client_id_token
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == projectId).first()
    if not task:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})
    _check_ownership(task, client_id)

    if task.status != TaskStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail={"ret": {"code": 400, "msg": f"Task status is {task.status}, expected pending"}},
        )

    task.status = TaskStatus.PROCESSING.value
    task.current_stage = TaskStage.INITIALIZING.value
    task.progress = 0
    es = (
        settings.alg2_expected_seconds
        if settings.alg_enabled and task.scene == "commodity"
        else settings.alg_expected_seconds
        if settings.alg_enabled
        else 15
    )
    task.remaining_time = _estimate_remaining(task, db, es)
    db.commit()

    task_files = db.query(TaskFile).filter(TaskFile.task_id == task_id).all()
    first_video = next(
        (f for f in task_files if f.fileName.lower().endswith(SUPPORTED_VIDEO_EXTS)),
        task_files[0] if task_files else None,
    )

    if first_video:
        logger.info("start task=%s file=%s", task_id, first_video.fileUrl)
        remote_path = first_video.fileUrl
        if not storage.object_exists(remote_path):
            logger.error("start: file not found %s", remote_path)
            task.status = TaskStatus.FAILED.value
            task.error_message = "file not uploaded yet"
            db.commit()
            raise HTTPException(
                status_code=400,
                detail={
                    "ret": {
                        "code": 400,
                        "msg": "file not uploaded yet, please upload via uploadInfos URL first",
                    }
                },
            )
        local_video = os.path.join(TASK_OUTPUT_DIR, str(task_id), os.path.basename(remote_path))
        submit_pipeline(task_id, local_video)
        logger.info("[start] task=%s pipeline submitted", task_id)
    else:
        task.status = TaskStatus.FAILED.value
        task.error_message = "no valid video file found"
        db.commit()
        raise HTTPException(
            status_code=400, detail={"ret": {"code": 400, "msg": "no valid video file found"}}
        )

    return StartTaskRsp(remainingTime=task.remaining_time)


@router.get("/{task_id}", response_model=GetTaskRsp)
def query_task(
    task_id: str,
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    client_id_token: tuple = Depends(get_current_client_id),
):
    """查询任务状态及输出文件."""
    client_id, token = client_id_token
    q = db.query(Task).filter(Task.id == task_id, Task.project_id == projectId)
    if client_id:
        q = q.filter(Task.client_id == client_id)
    task = q.first()
    if not task:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})

    download_infos = []
    output_roles = {"raw_model", "compressed_model"}
    output_files = (
        db.query(TaskFile)
        .filter(
            TaskFile.task_id == task.id,
            TaskFile.fileRole.in_(output_roles),
        )
        .all()
    )
    for f in output_files:
        download_infos.append(_gen_download_url(task.id, f, project_id=projectId, token=token))

    remaining = task.remaining_time
    if task.status == TaskStatus.PROCESSING.value:
        es = (
            settings.alg2_expected_seconds
            if settings.alg_enabled and task.scene == "commodity"
            else settings.alg_expected_seconds
            if settings.alg_enabled
            else 15
        )
        remaining = _estimate_remaining(task, db, es)

    return GetTaskRsp(
        taskId=task.id,
        status=task.status,
        currentStage=task.current_stage,
        progress=task.progress,
        remainingTime=remaining,
        scene=task.scene,
        errorMessage=task.error_message or "",
        downloadInfos=download_infos,
    )


@router.get("/{task_id}/download/{object_id:path}", tags=["fileTransfer"])
def download_file(
    task_id: str,
    object_id: str,
    projectId_h: str | None = Header(None, alias="projectId", max_length=20),
    projectId_q: str | None = Query(None, alias="projectId", max_length=20),
    auth_h: str | None = Header(None, alias="Authorization"),
    auth_q: str | None = Query(None, alias="Authorization"),
    db: Session = Depends(get_database),
):
    """下载任务输出文件."""
    from backend.core.auth import _auth_enabled

    token_str = auth_h or auth_q or ""
    token_str = token_str.replace("Bearer ", "")
    client_id = ""
    if token_str and _auth_enabled():
        payload = _decode_jwt(token_str)
        client_id = payload.get("client_id", "")
    elif _auth_enabled():
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    pid = projectId_h or projectId_q
    if not pid:
        raise HTTPException(
            status_code=422, detail={"ret": {"code": 422, "msg": "Missing projectId"}}
        )

    task = db.query(Task).filter(Task.id == task_id, Task.project_id == pid).first()
    if not task:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})
    _check_ownership(task, client_id)

    safe_name = _safe_filename(os.path.basename(object_id))
    task_file = (
        db.query(TaskFile)
        .filter(
            TaskFile.task_id == task_id,
            TaskFile.fileName == safe_name,
            TaskFile.fileRole.in_({"raw_model", "compressed_model"}),
        )
        .first()
    )
    if task_file:
        try:
            url = storage.get_presigned_url(task_file.fileUrl, expires=3600)
            return RedirectResponse(url=url)
        except Exception:
            pass

    fpath = os.path.join(TASK_OUTPUT_DIR, str(task.id), "output", safe_name)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "File not found"}})

    return FileResponse(fpath, filename=safe_name)
