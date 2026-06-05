"""Database configuration and session management."""
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import enum
from uuid import uuid4

from backend.core.config import settings


_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStage(str, enum.Enum):
    INITIALIZING = "initializing"
    EXTRACTING = "extracting"
    COLMAP = "colmap"
    TRAINING = "training"
    COMPRESSING = "compressing"
    COMPLETED = "completed"
    FAILED = "failed"


def _generate_task_id():
    ts = int(datetime.utcnow().timestamp() * 1000)
    return f"{ts}{uuid4().hex[:6]}"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(32), primary_key=True, default=_generate_task_id)
    project_id = Column(String(20), nullable=False, index=True)
    external_code = Column(String(256), nullable=False, index=True)
    scene = Column(String(32), nullable=False)
    status = Column(String(50), default=TaskStatus.PENDING.value)
    current_stage = Column(String(50), default=TaskStage.INITIALIZING.value)
    progress = Column(Integer, default=0)
    remaining_time = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    files = relationship("TaskFile", back_populates="task", cascade="all, delete-orphan")


class TaskFile(Base):
    __tablename__ = "task_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(32), ForeignKey("tasks.id"), nullable=False)
    fileName = Column(String(256), nullable=False)
    sha256 = Column(String(64), nullable=False)
    contentLength = Column(Integer, nullable=False)
    fileUrl = Column(String(1024), nullable=False)

    task = relationship("Task", back_populates="files")


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
