"""TaskRepository — 统一封装 Task / TaskFile 数据库操作。

设计要点：
  - 双模式 Session 管理：
    实例方法（API 层）：接收 Depends 注入的 Session，生命周期由请求管理
    静态方法（Worker 层）：自行创建 SessionLocal → 操作 → 关闭，线程安全
  - 静态方法返回 dict/list 而非 ORM 对象，避免跨 session 访问 detached 实例

使用示例：
  # API 层
  repo = TaskRepository(db)
  task = repo.get(task_id, project_id)

  # Worker 层
  TaskRepository.update_progress(task_id, "training", 50, status="processing")
"""

import logging
import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.core.database import SessionLocal, Task, TaskFile, TaskStatus

logger = logging.getLogger(__name__)


class TaskRepository:
    """Task 数据访问层。"""

    def __init__(self, db: Session):
        self.db = db

    # ── API 层（注入 Session）─────────────────────────────

    def get(self, task_id: str, project_id: str | None = None) -> Task | None:
        q = self.db.query(Task).filter(Task.id == task_id)
        if project_id:
            q = q.filter(Task.project_id == project_id)
        return q.first()

    def list_by_project(self, project_id: str) -> list[Task]:
        return (
            self.db.query(Task)
            .filter(Task.project_id == project_id)
            .order_by(Task.created_at.desc())
            .all()
        )

    def create(self, project_id: str, external_code: str, scene: str) -> Task:
        task = Task(
            project_id=project_id,
            external_code=external_code,
            scene=scene,
            status=TaskStatus.PENDING.value,
        )
        self.db.add(task)
        return task

    def get_output_files(self, task_id: str) -> list[TaskFile]:
        return (
            self.db.query(TaskFile)
            .filter(TaskFile.task_id == task_id, TaskFile.fileRole == "compressed_model")
            .all()
        )

    def find_file_by_name(
        self, task_id: str, filename: str, role: str = "compressed_model"
    ) -> TaskFile | None:
        return (
            self.db.query(TaskFile)
            .filter(
                TaskFile.task_id == task_id,
                TaskFile.fileRole == role,
                TaskFile.fileName == filename,
            )
            .first()
        )

    # ── Worker 层（独立 Session，线程安全）─────────────────

    @staticmethod
    def update_progress(
        task_id: str, stage: str, progress: int, status: str | None = None, error: str | None = None
    ) -> None:
        """更新任务进度。remaining_time 按 stub 15 秒线性递减估算。"""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.current_stage = stage
                task.progress = progress
                task.remaining_time = 0 if status == "completed" else max(0, 15 - progress // 7)
                if status:
                    task.status = status
                if error:
                    task.error_message = error
                if status == "completed":
                    task.completed_at = datetime.utcnow()
                db.commit()
                logger.info(
                    "task=%s stage=%s progress=%d status=%s",
                    task_id,
                    stage,
                    progress,
                    status or "-",
                )
        finally:
            db.close()

    @staticmethod
    def add_output_file(
        task_id: str, local_path: str, mime: str, storage_url: str | None = None
    ) -> TaskFile | None:
        db = SessionLocal()
        try:
            tf = TaskFile(
                task_id=task_id,
                fileName=os.path.basename(local_path),
                sha256="",
                contentLength=os.path.getsize(local_path),
                fileUrl=storage_url or local_path,
                fileRole="compressed_model",
                mimeType=mime,
            )
            db.add(tf)
            db.commit()
            db.refresh(tf)
            return tf
        except Exception:
            db.rollback()
            return None
        finally:
            db.close()

    @staticmethod
    def cleanup_expired_pending(hours: int) -> list[str]:
        """删除过期 pending 任务（DB + TaskFile 在同一事务中），返回已删除的 task_id 列表供磁盘清理。"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        db = SessionLocal()
        try:
            tasks = (
                db.query(Task)
                .filter(
                    Task.status == TaskStatus.PENDING.value,
                    Task.created_at < cutoff,
                )
                .all()
            )
            ids = [t.id for t in tasks]
            for t in tasks:
                db.query(TaskFile).filter(TaskFile.task_id == t.id).delete()
                db.delete(t)
            if tasks:
                db.commit()
            return ids
        finally:
            db.close()

    @staticmethod
    def cleanup_expired_completed(days: int) -> list[str]:
        """删除过期 completed 任务（DB + TaskFile 在同一事务中），返回已删除的 task_id 列表供磁盘清理。"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        db = SessionLocal()
        try:
            tasks = (
                db.query(Task)
                .filter(
                    Task.status == TaskStatus.COMPLETED.value,
                    Task.completed_at < cutoff,
                )
                .all()
            )
            ids = [t.id for t in tasks]
            for t in tasks:
                db.query(TaskFile).filter(TaskFile.task_id == t.id).delete()
                db.delete(t)
            if tasks:
                db.commit()
            return ids
        finally:
            db.close()
