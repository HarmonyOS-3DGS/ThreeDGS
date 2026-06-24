"""数据库连接配置与会话管理。

数据库设计文档：docs/database_design.md
⚠️ 修改 ORM 模型后请同步更新 docs/database_design.md 中的字段表、索引、状态流转等章节。

ORM 模型定义已迁移至 backend.core.models：
  - backend.core.models.task       → Task、TaskStatus、TaskStage、_generate_task_id
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

# 以下 import 必须在 Base 定义之后，因为 models/ 模块依赖 Base
# 延迟导入避免循环依赖：database.py → models/ → database.py 通过 sys.modules 缓存解决
from backend.core.models.task import (  # noqa: E402, F401
    Task,
    TaskStage,
    TaskStatus,
    _generate_task_id,
)
from backend.core.models.task_file import TaskFile  # noqa: E402, F401


def get_db():
    """依赖注入用 session generator。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_client_id_column():
    """迁移：为已有 tasks 表添加 client_id 列。"""
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    try:
        with engine.connect() as conn:
            conn.execute(
                text("ALTER TABLE tasks ADD COLUMN client_id VARCHAR(64) NOT NULL DEFAULT ''")
            )
            conn.commit()
    except SQLAlchemyError:
        pass


def _ensure_processing_started_at_column():
    """迁移：为已有 tasks 表添加 processing_started_at 列。"""
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN processing_started_at TIMESTAMP NULL"))
            conn.commit()
    except SQLAlchemyError:
        pass


def init_db():
    """自动建表（MVP 阶段无 Alembic 迁移）。"""
    Base.metadata.create_all(bind=engine)
    _ensure_client_id_column()
    _ensure_processing_started_at_column()
