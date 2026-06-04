"""
SQLAlchemy database models.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    """User account model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="user")  # admin, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    scenes = relationship("Scene", back_populates="owner", cascade="all, delete-orphan")


class Scene(Base):
    """3D Gaussian Splatting scene model."""
    __tablename__ = "scenes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    filename = Column(String(255), nullable=False)  # Original filename
    file_path = Column(String(500), nullable=False)  # Stored file path
    file_size = Column(Integer, nullable=False)  # File size in bytes
    file_format = Column(String(10), nullable=False)  # ply, splat, ksplat
    
    # Scene metadata (extracted or provided)
    num_gaussians = Column(Integer, nullable=True)
    scene_scale = Column(Float, nullable=True)
    has_sh = Column(Boolean, default=False)  # Has spherical harmonics
    sh_degree = Column(Integer, default=0)
    
    # Preview and status
    thumbnail_path = Column(String(500), nullable=True)
    status = Column(String(20), default="ready")  # uploading, processing, ready, error
    
    # Ownership
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_public = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_viewed_at = Column(DateTime, nullable=True)
    view_count = Column(Integer, default=0)
    
    # Relationships
    owner = relationship("User", back_populates="scenes")
