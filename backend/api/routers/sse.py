"""SSE 实时进度推送端点。

设计要点：
  - 使用 asyncio.to_thread 将同步 DB 查询放入线程池，避免阻塞事件循环
  - 每次轮询创建独立的 SessionLocal，用完即关，不持有长连接
  - 数据以 dict 形式跨越 thread/session 边界，避免 detached ORM 对象
  - 2 秒间隔 + "completed"/"failed" 时自动停止

为何不用 AsyncSession：MVP 阶段其他端点都是同步 Session，部分异步代价大。
asyncio.to_thread 方案对现有架构改动最小，且与 SQLite/PostgreSQL 均兼容。
"""

import asyncio
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from backend.core.auth import _verify_auth_key
from backend.core.database import SessionLocal, Task

router = APIRouter(prefix="/tasks", tags=["sse"])


def _verify_sse_auth(
    projectId_h: str | None = Header(None, alias="projectId"),
    projectId_q: str | None = Query(None, alias="projectId"),
    auth_h: str | None = Header(None, alias="Authorization"),
    auth_q: str | None = Query(None, alias="Authorization"),
):
    token = auth_h or auth_q
    _verify_auth_key(token)
    pid = projectId_h or projectId_q
    if not pid:
        raise HTTPException(
            status_code=422, detail={"ret": {"code": 422, "msg": "Missing projectId"}}
        )
    return pid


def _fetch_task_status(task_id: str, project_id: str) -> dict | None:
    """同步查询 + 返回纯 dict。

    返回 dict 而非 ORM 对象：调用方在另一个线程，ORM 对象跨 session 不可用。
    """
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
        if not task:
            return None
        return {
            "status": task.status,
            "stage": task.current_stage,
            "progress": task.progress,
            "remainingTime": task.remaining_time,
            "updatedAt": task.updated_at.isoformat() if task.updated_at else "",
        }
    finally:
        db.close()


async def task_event_generator(task_id: str, project_id: str):
    while True:
        data = await asyncio.to_thread(_fetch_task_status, task_id, project_id)

        if data is None:
            yield {
                "event": "error",
                "data": json.dumps({"ret": {"code": 404, "msg": "Task not found"}}),
            }
            break

        yield {"event": "status", "data": json.dumps(data)}

        if data["status"] in ("completed", "failed"):
            yield {"event": "done", "data": json.dumps({"finalStatus": data["status"]})}
            break

        await asyncio.sleep(2)


@router.get("/{task_id}/events")
async def task_events(
    task_id: str,
    pid: str = Depends(_verify_sse_auth),
):
    # 快速预检任务是否存在
    data = await asyncio.to_thread(_fetch_task_status, task_id, pid)
    if data is None:
        raise HTTPException(status_code=404, detail={"ret": {"code": 404, "msg": "Task not found"}})

    return EventSourceResponse(task_event_generator(task_id, pid))
