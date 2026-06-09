"""Database configuration and session management.

Database design doc: docs/database_design.md
⚠️ 修改 ORM 模型后请同步更新 docs/database_design.md 中的字段表、索引、状态流转等章节。

ORM 模型定义已迁移至 backend.core.models：
  - backend.core.models.task       → Task, TaskStatus, TaskStage, _generate_task_id
  - backend.core.models.task_file  → TaskFile
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.core.config import settings

_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ORM 模型 —— 从 models/ 子模块导入后在此重导出，保持向后兼容
from backend.core.models.task import Task, TaskStatus, TaskStage, _generate_task_id  # noqa: E402, F401
from backend.core.models.task_file import TaskFile  # noqa: E402, F401


def get_db():
    """Yield a database session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
