"""
System information and health check routes.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, Scene
from schemas import SystemInfo, StatsResponse
from auth import get_current_admin, get_current_user

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/info", response_model=SystemInfo)
def get_system_info():
    """Get system information and capabilities."""
    return SystemInfo(
        name="3DGS Demo API",
        version="1.0.0",
        demo_mode=True,
        features=[
            "JWT Authentication",
            "3DGS Scene Upload/Download",
            "PLY/SPLAT/KSPLAT Support",
            "Scene Metadata Extraction",
            "Public/Private Scenes",
            "Web Viewer Integration",
        ],
        supported_formats=["ply", "splat", "ksplat"]
    )


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "3dgs-demo-api"}


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get system statistics (admin only)."""
    total_users = db.query(User).count()
    total_scenes = db.query(Scene).count()
    total_views = db.query(Scene).with_entities(Scene.view_count).all()
    total_view_count = sum(v[0] for v in total_views) if total_views else 0
    
    # Calculate storage used
    from sqlalchemy import func
    storage_used = db.query(func.sum(Scene.file_size)).scalar() or 0
    
    return StatsResponse(
        total_users=total_users,
        total_scenes=total_scenes,
        total_views=total_view_count,
        storage_used=storage_used
    )
