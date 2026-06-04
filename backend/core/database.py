"""Database configuration and session management."""
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid
import enum

from backend.core.config import settings


_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ProjectStatus(str, enum.Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    COLMAP = "colmap"
    TRAINING = "training"
    COMPRESSING = "compressing"
    COMPLETED = "completed"
    FAILED = "failed"


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    status = Column(String(50), default=ProjectStatus.PENDING.value)
    current_stage = Column(String(50), default="pending")
    progress = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Storage paths
    raw_upload_path = Column(String(512), nullable=True)
    frames_dir = Column(String(512), nullable=True)
    colmap_dir = Column(String(512), nullable=True)
    model_path = Column(String(512), nullable=True)
    compressed_path = Column(String(512), nullable=True)
    preview_path = Column(String(512), nullable=True)


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
