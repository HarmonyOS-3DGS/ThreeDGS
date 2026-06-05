"""Pydantic schemas for task API."""
from typing import Optional
from pydantic import BaseModel, Field


class ConnectRet(BaseModel):
    code: int = 0
    msg: str = "success"


class FileInfo(BaseModel):
    fileName: str = Field(..., max_length=256)
    sha256: Optional[str] = Field(None, max_length=64)
    contentLength: Optional[int] = None
    fileUrl: str


class CreateTaskReq(BaseModel):
    externalCode: str = Field(..., max_length=256)
    fileInfos: list[FileInfo] = Field(..., min_length=1, max_length=3)
    scene: str = Field(..., max_length=32)


class CreateTaskRsp(BaseModel):
    ret: ConnectRet = ConnectRet()
    taskId: str
    fileInfos: list[FileInfo]


class StartTaskRsp(BaseModel):
    ret: ConnectRet = ConnectRet()
    remainingTime: int


class GetTaskRsp(BaseModel):
    ret: ConnectRet = ConnectRet()
    status: str
    currentStage: str
    progress: int
    remainingTime: int
    downloadInfos: list[FileInfo] = []


class TaskStatusEvent(BaseModel):
    status: str
    stage: str
    progress: int
    remainingTime: int
    updatedAt: str
