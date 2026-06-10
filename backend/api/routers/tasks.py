"""任务管理路由：创建、列表、启动、查询、下载。"""

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
from backend.core.auth import verify_app_auth, verify_project_auth
from backend.core.config import TASK_OUTPUT_DIR, settings
from backend.core.database import Task, TaskFile, TaskStage, TaskStatus
from backend.core.storage import storage
from backend.core.task_publisher import submit_pipeline

router = APIRouter(prefix="/tasks", tags=["taskManagement"])


def _safe_filename(filename: str) -> str:
    """Sanitize filename, prevent path traversal."""
    return os.path.basename(filename)


def _gen_upload_url(task_id: str, fi: FileInfo) -> UrlInfo:
    """为单个文件生成预签名上传 URL。"""
    safe_name = _safe_filename(fi.fileName)
    object_name = f"tasks/{task_id}/{safe_name}"
    try:
        url = storage.get_presigned_put_url(object_name, expires=3600)
        headers = {}
    except Exception:
        url = f"/tasks/{task_id}/upload/{safe_name}"
        headers = {"Authorization": settings.api_key} if settings.api_key else {}
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


def _gen_download_url(task_id: str, tf: TaskFile, project_id: str = "") -> UrlInfo:
    """为输出文件生成预签名下载 URL。"""
    try:
        url = storage.get_presigned_url(tf.fileUrl, expires=3600)
    except Exception:
        url = f"/tasks/{task_id}/download/{tf.fileName}"
        if project_id:
            params = {"projectId": project_id}
            if settings.api_key:
                params["Authorization"] = settings.api_key
            url += f"?{urlencode(params)}"
    return UrlInfo(objectId=tf.fileName, fileName=tf.fileName, url=url, method="GET")


@router.get("", response_model=TaskListResponse)
def list_tasks(
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    _auth: str = Depends(verify_project_auth),
):
    """列出指定项目的所有任务."""
    tasks = (
        db.query(Task).filter(Task.project_id == projectId).order_by(Task.created_at.desc()).all()
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


@router.post("", response_model=CreateTaskRsp)
def create_task(
    request: CreateTaskReq,
    projectId: str = Header(..., max_length=20),
    db: Session = Depends(get_database),
    _auth: str = Depends(verify_app_auth),
):
    """创建3DGS任务。仅接收 JSON 元数据，返回预签名上传 URL。"""
    task = Task(
        project_id=projectId,
        external_code=request.externalCode,
        scene=request.scene,
        status=TaskStatus.PENDING.value,
        current_stage=TaskStage.INITIALIZING.value,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    upload_infos = []
    for fi in request.fileInfos:
        safe_name = _safe_filename(fi.fileName)
        url_info = _gen_upload_url(task.id, fi)
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
    return CreateTaskRsp(taskId=task.id, uploadInfos=upload_infos)


@router.put("/{task_id}/upload/{object_id:path}", tags=["fileTransfer"])
async def upload_file(
    task_id: str,
    object_id: str,
    request: Request,
    _auth: str = Depends(verify_app_auth),
):
    """本地模式：接收客户端 PUT 的文件，写入本地存储。"""
    safe_name = _safe_filename(os.path.basename(object_id))
    task_dir = os.path.join(TASK_OUTPUT_DIR, str(task_id))
    await aiofiles.os.makedirs(task_dir, exist_ok=True)

    local_path = os.path.join(task_dir, safe_name)
    if os.path.isfile(local_path):
        raise HTTPException(status_code=400, detail={"ret": {"code": 400, "msg": "文件已存在"}})

    content = await request.body()

    async with aiofiles.open(local_path, "wb") as f:
        await f.write(content)

    return {"ret": {"code": 0, "msg": "success"}, "fileName": safe_name, "size": len(content)}


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
        # 确保文件已上传并下载到共享卷
        remote_path = first_video.fileUrl
        local_video = os.path.join(TASK_OUTPUT_DIR, str(task_id), os.path.basename(remote_path))
        if not os.path.exists(local_video):
            try:
                storage.download_file(remote_path, local_video)
            except Exception:
                pass
        if not os.path.exists(local_video):
            task.status = TaskStatus.FAILED.value
            task.error_message = "文件尚未上传"
            db.commit()
            raise HTTPException(
                status_code=400,
                detail={
                    "ret": {
                        "code": 400,
                        "msg": "文件尚未上传，请先通过 uploadInfos 中的 URL 上传文件",
                    }
                },
            )
        submit_pipeline(task_id, local_video)
    else:
        task.status = TaskStatus.FAILED.value
        task.error_message = "没有找到可处理的视频文件"
        db.commit()
        raise HTTPException(
            status_code=400, detail={"ret": {"code": 400, "msg": "没有找到可处理的视频文件"}}
        )

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
    output_files = (
        db.query(TaskFile)
        .filter(
            TaskFile.task_id == task.id,
            TaskFile.fileRole == "compressed_model",
        )
        .all()
    )
    for f in output_files:
        download_infos.append(_gen_download_url(task.id, f, project_id=projectId))

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
    from backend.core.auth import _verify_auth_key

    _verify_auth_key(auth_h or auth_q)
    pid = projectId_h or projectId_q
    if not pid:
        raise HTTPException(
            status_code=422, detail={"ret": {"code": 422, "msg": "Missing projectId"}}
        )

    task = db.query(Task).filter(Task.id == task_id, Task.project_id == pid).first()
    if not task:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})

    safe_name = _safe_filename(os.path.basename(object_id))
    task_file = (
        db.query(TaskFile)
        .filter(
            TaskFile.task_id == task_id,
            TaskFile.fileRole == "compressed_model",
            TaskFile.fileName == safe_name,
        )
        .first()
    )
    if task_file:
        try:
            url = storage.get_presigned_url(task_file.fileUrl, expires=3600)
            return RedirectResponse(url=url)
        except Exception:
            pass

    fpath = os.path.join(TASK_OUTPUT_DIR, str(task.id), "compressed", safe_name)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "File not found"}})

    return FileResponse(fpath, filename=safe_name)
