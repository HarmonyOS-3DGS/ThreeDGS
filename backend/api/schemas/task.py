"""Pydantic schemas for task API."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


class FileInfo(BaseModel):
    """Schema for file metadata in task."""
    original_filename: str
    sha256: str
    file_size: int
    file_path: str


class TaskCreateResponse(BaseModel):
    """Schema for create task response."""
    task_id: UUID
    files: list[FileInfo]


class TaskStartResponse(BaseModel):
    """Schema for start task response."""
    code: int = 0
    msg: str = "success"
    remaining_time: int


class TaskQueryResponse(BaseModel):
    """Schema for query task response."""
    code: int = 0
    status: str
    current_stage: str
    progress: int
    remaining_time: int
    output_files: list[FileInfo] = []


class TaskStatusEvent(BaseModel):
    """Schema for SSE status events."""
    status: str
    stage: str
    progress: int
    remaining_time: int
    updated_at: str
