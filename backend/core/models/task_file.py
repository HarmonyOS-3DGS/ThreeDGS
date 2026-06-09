"""TaskFile ORM model."""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.core.database import Base


class TaskFile(Base):
    __tablename__ = "task_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(32), ForeignKey("tasks.id"), nullable=False)
    fileName = Column(String(256), nullable=False)
    sha256 = Column(String(64), nullable=False)
    contentLength = Column(Integer, nullable=False)
    fileUrl = Column(String(1024), nullable=False)
    fileRole = Column(String(50), nullable=False, default="source_video")
    mimeType = Column(String(128), nullable=True)

    task = relationship("Task", back_populates="files")
