"""Pydantic schemas for task API."""
from typing import Literal, Optional
from pydantic import BaseModel, Field

VALID_FILE_ROLES = {"source_video", "source_images", "compressed_model", "pose_data"}


class ConnectRet(BaseModel):
    code: int = 0
    msg: str = "success"


class FileInfo(BaseModel):
    fileName: str = Field(..., max_length=256)
    sha256: Optional[str] = Field(None, max_length=64)
    contentLength: Optional[int] = None
    fileUrl: str = ""
    fileRole: str = "source_video"
    mimeType: Optional[str] = None


class CreateTaskReq(BaseModel):
    externalCode: str = Field(..., max_length=256)
    fileInfos: list[FileInfo] = Field(..., min_length=1, max_length=3)
    scene: Literal["commodity", "indoor", "outdoor"]


class CreateTaskRsp(BaseModel):
    ret: ConnectRet = ConnectRet()
    taskId: str
    fileInfos: list[FileInfo]


class StartTaskRsp(BaseModel):
    ret: ConnectRet = ConnectRet()
    remainingTime: int


class GetTaskRsp(BaseModel):
    ret: ConnectRet = ConnectRet()
    taskId: str
    status: str
    currentStage: str
    progress: int
    remainingTime: int
    scene: str
    downloadInfos: list[FileInfo] = []


class TaskListResponse(BaseModel):
    ret: ConnectRet = ConnectRet()
    items: list[GetTaskRsp]
    total: int


class TaskStatusEvent(BaseModel):
    status: str
    stage: str
    progress: int
    remainingTime: int
    updatedAt: str
