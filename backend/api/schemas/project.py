"""Pydantic schemas for project API."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""
    name: str = Field(..., min_length=1, max_length=255)


class ProjectResponse(BaseModel):
    """Schema for project response."""
    id: UUID
    name: str
    status: str
    current_stage: str
    progress: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """Schema for listing projects."""
    items: list[ProjectResponse]
    total: int


class ProjectStatusEvent(BaseModel):
    """Schema for SSE status events."""
    status: str
    stage: str
    progress: int
    updated_at: str
