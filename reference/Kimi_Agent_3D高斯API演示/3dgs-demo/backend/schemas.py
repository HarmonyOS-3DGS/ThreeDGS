"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# ============== Auth Schemas ==============

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)


class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenPayload(BaseModel):
    sub: Optional[int] = None
    exp: Optional[datetime] = None


# ============== Scene Schemas ==============

class SceneBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_public: bool = False


class SceneCreate(SceneBase):
    pass


class SceneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_public: Optional[bool] = None


class SceneResponse(SceneBase):
    id: int
    filename: str
    file_size: int
    file_format: str
    num_gaussians: Optional[int]
    scene_scale: Optional[float]
    has_sh: bool
    sh_degree: int
    status: str
    owner_id: int
    view_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SceneListResponse(BaseModel):
    total: int
    items: List[SceneResponse]


class SceneDetailResponse(SceneResponse):
    download_url: Optional[str] = None
    viewer_url: Optional[str] = None


# ============== System Schemas ==============

class SystemInfo(BaseModel):
    name: str
    version: str
    demo_mode: bool
    features: List[str]
    supported_formats: List[str]


class StatsResponse(BaseModel):
    total_users: int
    total_scenes: int
    total_views: int
    storage_used: int
