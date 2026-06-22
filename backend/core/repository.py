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

from backend.core.config import settings
from backend.core.database import SessionLocal, Task, TaskFile, TaskStage, TaskStatus

logger = logging.getLogger(__name__)


class TaskRepository:
    """Task 数据访问层。"""

    def __init__(self, db: Session):
        self.db = db

    # ── API 层（注入 Session）─────────────────────────────

    def get(
        self, task_id: str, project_id: str | None = None, client_id: str | None = None
    ) -> Task | None:
        q = self.db.query(Task).filter(Task.id == task_id)
        if project_id:
            q = q.filter(Task.project_id == project_id)
        if client_id:
            q = q.filter(Task.client_id == client_id)
        return q.first()

    def list_by_project(self, project_id: str, client_id: str | None = None) -> list[Task]:
        q = self.db.query(Task).filter(Task.project_id == project_id)
        if client_id:
            q = q.filter(Task.client_id == client_id)
        return q.order_by(Task.created_at.desc()).all()

    def create(self, project_id: str, external_code: str, scene: str, client_id: str = "") -> Task:
        task = Task(
            project_id=project_id,
            external_code=external_code,
            scene=scene,
            client_id=client_id,
            status=TaskStatus.PENDING.value,
        )
        self.db.add(task)
        return task

    def get_output_files(self, task_id: str, roles: set[str] | None = None) -> list[TaskFile]:
        roles = roles or {"raw_model", "compressed_model"}
        return (
            self.db.query(TaskFile)
            .filter(TaskFile.task_id == task_id, TaskFile.fileRole.in_(roles))
            .all()
        )

    def find_file_by_name(
        self, task_id: str, filename: str, role: str = "raw_model"
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

    # ── 排队估算（API / Worker 共用）─────────────────────

    @staticmethod
    def _max_duration_for_scene(scene: str) -> int:
        """根据场景获取任务的最大超时秒数。"""
        if scene == "commodity":
            return settings.alg2_max_seconds
        return settings.alg_max_seconds if settings.alg_enabled else 3600

    @staticmethod
    def estimate_queue_wait(db: Session, task: Task, es: int) -> int:
        """估算包含排队时间的剩余秒数。

        考虑当前正在运行且未超时的 processing 任务，
        以及排在当前任务之前的 pending 任务。
        超过最大时长的 processing 任务不计入排队（已失效）。
        """
        now = datetime.utcnow()
        processing_ahead = 0
        for t in (
            db.query(Task)
            .filter(
                Task.status == TaskStatus.PROCESSING.value,
                Task.created_at < task.created_at,
                Task.id != task.id,
            )
            .all()
        ):
            max_dur = TaskRepository._max_duration_for_scene(t.scene)
            if t.updated_at and (now - t.updated_at).total_seconds() < max_dur:
                processing_ahead += 1

        pending_ahead = (
            db.query(Task)
            .filter(
                Task.status == TaskStatus.PENDING.value,
                Task.created_at < task.created_at,
            )
            .count()
        )
        wc = max(1, settings.worker_count)
        own = max(0, es - task.progress * es // 100)
        return own + (processing_ahead + pending_ahead) * es // wc

    @staticmethod
    def cleanup_expired_processing() -> list[str]:
        """标记超时的 processing 任务为 failed，返回 task_id 列表。

        根据任务的 scene 判断其最大允许运行时间，超过则视为已失效。
        防止 Worker 崩溃后任务状态永久卡在 processing。
        """
        now = datetime.utcnow()
        db = SessionLocal()
        try:
            tasks = db.query(Task).filter(Task.status == TaskStatus.PROCESSING.value).all()
            expired = []
            for t in tasks:
                max_dur = TaskRepository._max_duration_for_scene(t.scene)
                last_active = t.updated_at or t.created_at
                if last_active and (now - last_active).total_seconds() >= max_dur:
                    t.status = TaskStatus.FAILED.value
                    t.current_stage = TaskStage.FAILED.value
                    t.error_message = "任务执行超时，已被系统自动终止"
                    t.completed_at = now
                    expired.append(t.id)
            if expired:
                db.commit()
                logger.info("cleanup_expired_processing: marked %d tasks as failed", len(expired))
            return expired
        finally:
            db.close()

    # ── Worker 层（独立 Session，线程安全）─────────────────

    @staticmethod
    def update_progress(
        task_id: str,
        stage: str,
        progress: int,
        status: str | None = None,
        error: str | None = None,
        expected_seconds: int | None = None,
    ) -> None:
        """更新任务进度。remaining_time 按预期时长线性递减估算。"""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.current_stage = stage
                task.progress = progress
                es = expected_seconds or (
                    settings.alg_expected_seconds if settings.alg_enabled else 15
                )
                task.remaining_time = (
                    0 if status == "completed" else TaskRepository.estimate_queue_wait(db, task, es)
                )
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
                    task.status,
                )
        finally:
            db.close()

    @staticmethod
    def add_output_file(
        task_id: str,
        local_path: str,
        mime: str,
        storage_url: str | None = None,
        file_role: str = "raw_model",
    ) -> TaskFile | None:
        db = SessionLocal()
        try:
            tf = TaskFile(
                task_id=task_id,
                fileName=os.path.basename(local_path),
                sha256="",
                contentLength=os.path.getsize(local_path),
                fileUrl=storage_url or local_path,
                fileRole=file_role,
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
