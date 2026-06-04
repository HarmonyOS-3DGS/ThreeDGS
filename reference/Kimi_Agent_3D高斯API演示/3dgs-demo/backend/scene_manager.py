"""
3D Gaussian Splatting scene management module.
Handles file storage, metadata extraction, and scene operations.
"""
import os
import shutil
import struct
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from models import Scene, User
from schemas import SceneCreate, SceneUpdate
from config import get_settings

settings = get_settings()

# Ensure scenes directory exists
os.makedirs(settings.SCENES_DIR, exist_ok=True)


def get_scene_file_path(scene_id: int, filename: str) -> str:
    """Generate storage path for a scene file."""
    ext = Path(filename).suffix.lower()
    return os.path.join(settings.SCENES_DIR, f"scene_{scene_id}{ext}")


def extract_ply_metadata(file_path: str) -> dict:
    """Extract metadata from a PLY file.
    
    PLY format structure:
    - Header with element counts and property definitions
    - Data section (binary or ASCII)
    
    For 3DGS, we look for:
    - element vertex count (number of Gaussians)
    - Properties: x,y,z (position), nx,ny,nz, f_dc_* (SH), opacity, scale_*, rot_*
    """
    metadata = {
        "num_gaussians": 0,
        "has_sh": False,
        "sh_degree": 0,
        "scene_scale": None,
    }
    
    try:
        with open(file_path, 'rb') as f:
            # Read header
            header_lines = []
            while True:
                line = f.readline().decode('ascii', errors='ignore').strip()
                header_lines.append(line)
                if line == "end_header":
                    break
                if len(header_lines) > 100:  # Safety limit
                    break
            
            # Parse header
            num_vertices = 0
            properties = []
            format_type = "ascii"
            
            for line in header_lines:
                parts = line.split()
                if not parts:
                    continue
                
                if parts[0] == "element" and parts[1] == "vertex":
                    num_vertices = int(parts[2])
                elif parts[0] == "property":
                    prop_name = parts[-1]
                    properties.append(prop_name)
                elif parts[0] == "format":
                    format_type = parts[1]
            
            metadata["num_gaussians"] = num_vertices
            
            # Check for spherical harmonics
            sh_coeffs = [p for p in properties if p.startswith("f_dc_") or p.startswith("f_rest_")]
            metadata["has_sh"] = len(sh_coeffs) > 0
            
            # Estimate SH degree
            if metadata["has_sh"]:
                f_dc_count = len([p for p in properties if p.startswith("f_dc_")])
                if f_dc_count >= 9:
                    metadata["sh_degree"] = 3
                elif f_dc_count >= 4:
                    metadata["sh_degree"] = 2
                elif f_dc_count >= 1:
                    metadata["sh_degree"] = 1
            
            # Try to estimate scene scale from first few vertices
            if num_vertices > 0 and format_type == "binary_little_endian":
                # Skip to data section
                # Calculate property sizes
                prop_sizes = []
                for line in header_lines:
                    parts = line.split()
                    if parts[0] == "property":
                        dtype = parts[1]
                        if dtype in ["float", "float32"]:
                            prop_sizes.append(4)
                        elif dtype in ["double", "float64"]:
                            prop_sizes.append(8)
                        elif dtype in ["uchar", "uint8"]:
                            prop_sizes.append(1)
                        elif dtype in ["int", "int32"]:
                            prop_sizes.append(4)
                        else:
                            prop_sizes.append(4)  # Default
                
                vertex_size = sum(prop_sizes)
                if vertex_size > 0 and num_vertices > 0:
                    # Read first vertex position
                    x_idx = next((i for i, p in enumerate(properties) if p == "x"), -1)
                    y_idx = next((i for i, p in enumerate(properties) if p == "y"), -1)
                    z_idx = next((i for i, p in enumerate(properties) if p == "z"), -1)
                    
                    if x_idx >= 0:
                        offset = sum(prop_sizes[:x_idx])
                        f.seek(len(b'\n'.join([l.encode() for l in header_lines])) + len(b'\n') + offset)
                        # Read a sample of positions to estimate scale
                        sample_size = min(100, num_vertices)
                        positions = []
                        for _ in range(sample_size):
                            try:
                                pos_data = f.read(12)  # 3 floats
                                if len(pos_data) == 12:
                                    x, y, z = struct.unpack('fff', pos_data)
                                    positions.append((x, y, z))
                                else:
                                    f.seek(vertex_size - 12, 1)  # Skip rest of vertex
                            except:
                                break
                        
                        if positions:
                            # Calculate bounding box diagonal as scene scale
                            xs = [p[0] for p in positions]
                            ys = [p[1] for p in positions]
                            zs = [p[2] for p in positions]
                            diag = ((max(xs)-min(xs))**2 + (max(ys)-min(ys))**2 + (max(zs)-min(zs))**2) ** 0.5
                            metadata["scene_scale"] = round(diag, 4)
    
    except Exception as e:
        print(f"Error extracting PLY metadata: {e}")
    
    return metadata


def create_scene(db: Session, scene_data: SceneCreate, file_path: str, 
                 filename: str, file_size: int, owner_id: int) -> Scene:
    """Create a new scene record in the database."""
    
    # Extract metadata from file
    metadata = extract_ply_metadata(file_path)
    
    # Determine file format
    ext = Path(filename).suffix.lower().lstrip('.')
    
    scene = Scene(
        name=scene_data.name,
        description=scene_data.description,
        filename=filename,
        file_path=file_path,
        file_size=file_size,
        file_format=ext,
        num_gaussians=metadata.get("num_gaussians"),
        scene_scale=metadata.get("scene_scale"),
        has_sh=metadata.get("has_sh", False),
        sh_degree=metadata.get("sh_degree", 0),
        status="ready",
        owner_id=owner_id,
        is_public=scene_data.is_public,
    )
    
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


def update_scene(db: Session, scene: Scene, update_data: SceneUpdate) -> Scene:
    """Update scene metadata."""
    if update_data.name is not None:
        scene.name = update_data.name
    if update_data.description is not None:
        scene.description = update_data.description
    if update_data.is_public is not None:
        scene.is_public = update_data.is_public
    
    scene.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(scene)
    return scene


def delete_scene(db: Session, scene: Scene) -> bool:
    """Delete a scene and its associated files."""
    try:
        # Delete file if exists
        if os.path.exists(scene.file_path):
            os.remove(scene.file_path)
        
        # Delete thumbnail if exists
        if scene.thumbnail_path and os.path.exists(scene.thumbnail_path):
            os.remove(scene.thumbnail_path)
        
        db.delete(scene)
        db.commit()
        return True
    except Exception as e:
        print(f"Error deleting scene: {e}")
        db.rollback()
        return False


def get_user_scenes(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> Tuple[List[Scene], int]:
    """Get all scenes owned by a user."""
    query = db.query(Scene).filter(Scene.owner_id == user_id)
    total = query.count()
    scenes = query.order_by(Scene.created_at.desc()).offset(skip).limit(limit).all()
    return scenes, total


def get_public_scenes(db: Session, skip: int = 0, limit: int = 100) -> Tuple[List[Scene], int]:
    """Get all public scenes."""
    query = db.query(Scene).filter(Scene.is_public == True, Scene.status == "ready")
    total = query.count()
    scenes = query.order_by(Scene.created_at.desc()).offset(skip).limit(limit).all()
    return scenes, total


def get_scene_by_id(db: Session, scene_id: int) -> Optional[Scene]:
    """Get scene by ID."""
    return db.query(Scene).filter(Scene.id == scene_id).first()


def increment_view_count(db: Session, scene: Scene):
    """Increment scene view count and update last viewed time."""
    scene.view_count += 1
    scene.last_viewed_at = datetime.utcnow()
    db.commit()
