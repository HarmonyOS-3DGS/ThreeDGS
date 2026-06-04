"""
Scene management API routes.
Handles 3D Gaussian Splatting scene CRUD operations.
"""
import os
import shutil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from models import User, Scene
from schemas import (
    SceneCreate, SceneUpdate, SceneResponse, 
    SceneListResponse, SceneDetailResponse
)
from auth import get_current_user, get_optional_user
from scene_manager import (
    create_scene, update_scene, delete_scene,
    get_user_scenes, get_public_scenes, get_scene_by_id,
    increment_view_count, get_scene_file_path, settings
)

router = APIRouter(prefix="/scenes", tags=["Scenes"])


@router.get("", response_model=SceneListResponse)
def list_scenes(
    mine_only: bool = Query(False, description="Only show my scenes"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """List scenes - public scenes or user's own scenes."""
    if mine_only and current_user:
        scenes, total = get_user_scenes(db, current_user.id, skip, limit)
    else:
        # Return public scenes + user's own scenes if authenticated
        scenes, total = get_public_scenes(db, skip, limit)
        if current_user:
            user_scenes, user_total = get_user_scenes(db, current_user.id, skip, limit)
            # Merge and deduplicate
            seen_ids = {s.id for s in scenes}
            for s in user_scenes:
                if s.id not in seen_ids:
                    scenes.append(s)
            total = len(scenes)
    
    return {"total": total, "items": scenes}


@router.post("", response_model=SceneResponse, status_code=status.HTTP_201_CREATED)
def upload_scene(
    name: str = Form(..., min_length=1, max_length=100),
    description: Optional[str] = Form(None),
    is_public: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a new 3D Gaussian Splatting scene (PLY/SPLAT/K SPLAT file)."""
    # Validate file type
    allowed_extensions = {'.ply', '.splat', '.ksplat'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024:.0f}MB"
        )
    
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file"
        )
    
    try:
        # Create scene data object
        scene_data = SceneCreate(name=name, description=description, is_public=is_public)
        
        # Create a temporary placeholder to get an ID
        temp_scene = Scene(
            name=scene_data.name,
            description=scene_data.description,
            filename=file.filename,
            file_path="",  # Will update after we have ID
            file_size=file_size,
            file_format=file_ext.lstrip('.'),
            status="uploading",
            owner_id=current_user.id,
            is_public=scene_data.is_public,
        )
        db.add(temp_scene)
        db.commit()
        db.refresh(temp_scene)
        
        # Now save file with proper path
        file_path = get_scene_file_path(temp_scene.id, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Update scene with file path and extract metadata
        temp_scene.file_path = file_path
        temp_scene.status = "ready"
        
        # Extract metadata
        metadata = __import__('scene_manager', fromlist=['extract_ply_metadata']).extract_ply_metadata(file_path)
        temp_scene.num_gaussians = metadata.get("num_gaussians")
        temp_scene.scene_scale = metadata.get("scene_scale")
        temp_scene.has_sh = metadata.get("has_sh", False)
        temp_scene.sh_degree = metadata.get("sh_degree", 0)
        
        db.commit()
        db.refresh(temp_scene)
        
        return temp_scene
        
    except Exception as e:
        # Cleanup on error
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload scene: {str(e)}"
        )


@router.get("/{scene_id}", response_model=SceneDetailResponse)
def get_scene(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get scene details by ID."""
    scene = get_scene_by_id(db, scene_id)
    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene not found"
        )
    
    # Check access permissions
    if not scene.is_public and (not current_user or scene.owner_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Increment view count
    increment_view_count(db, scene)
    
    # Build response with URLs
    response = SceneDetailResponse.from_orm(scene)
    response.download_url = f"/api/v1/scenes/{scene_id}/download"
    response.viewer_url = f"/api/v1/scenes/{scene_id}/viewer"
    
    return response


@router.put("/{scene_id}", response_model=SceneResponse)
def update_scene_endpoint(
    scene_id: int,
    update_data: SceneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update scene metadata."""
    scene = get_scene_by_id(db, scene_id)
    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene not found"
        )
    
    if scene.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this scene"
        )
    
    updated = update_scene(db, scene, update_data)
    return updated


@router.delete("/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene_endpoint(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a scene."""
    scene = get_scene_by_id(db, scene_id)
    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene not found"
        )
    
    if scene.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this scene"
        )
    
    success = delete_scene(db, scene)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete scene"
        )
    
    return None


@router.get("/{scene_id}/download")
def download_scene(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Download scene file."""
    scene = get_scene_by_id(db, scene_id)
    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene not found"
        )
    
    # Check access permissions
    if not scene.is_public and (not current_user or scene.owner_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if not os.path.exists(scene.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene file not found"
        )
    
    return FileResponse(
        path=scene.file_path,
        filename=scene.filename,
        media_type="application/octet-stream"
    )


@router.get("/{scene_id}/raw")
def get_scene_raw(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get scene file content directly (for web viewer)."""
    scene = get_scene_by_id(db, scene_id)
    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene not found"
        )
    
    # Check access permissions
    if not scene.is_public and (not current_user or scene.owner_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if not os.path.exists(scene.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene file not found"
        )
    
    # Set appropriate content type based on format
    content_types = {
        'ply': 'application/octet-stream',
        'splat': 'application/octet-stream',
        'ksplat': 'application/octet-stream',
    }
    media_type = content_types.get(scene.file_format, 'application/octet-stream')
    
    return FileResponse(
        path=scene.file_path,
        media_type=media_type
    )
