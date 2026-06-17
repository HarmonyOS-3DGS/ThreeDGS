"""Task ORM model, status/stage enums, and ID generation."""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.core.database import Base
from backend.core.id_generator import generate_task_id as _generate_task_id


class TaskStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStage(enum.StrEnum):
    INITIALIZING = "initializing"
    EXTRACTING = "extracting"
    COLMAP = "colmap"
    TRAINING = "training"
    COMPRESSING = "compressing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(32), primary_key=True, default=_generate_task_id)
    project_id = Column(String(20), nullable=False, index=True)
    external_code = Column(String(256), nullable=False, index=True)
    client_id = Column(String(64), nullable=False, default="", index=True)
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
