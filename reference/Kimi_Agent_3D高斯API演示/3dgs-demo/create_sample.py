"""
Generate a sample 3D Gaussian Splatting PLY file for testing.
Creates a simple point cloud with random Gaussians forming a cube shape.
"""
import struct
import numpy as np
import os

OUTPUT_DIR = "scenes"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_sample_ply(filename: str, num_points: int = 1000):
    """Generate a sample PLY file with random 3D Gaussians."""
    
    # Generate random positions in a cube
    np.random.seed(42)
    positions = np.random.randn(num_points, 3) * 2.0  # Gaussian distribution
    
    # Random colors (SH DC coefficients)
    colors = np.random.rand(num_points, 3) * 0.5 + 0.25  # Soft colors
    
    # Random opacity
    opacity = np.random.rand(num_points) * 0.8 + 0.2
    
    # Random scale (log space)
    scales = np.random.rand(num_points, 3) * 2.0 - 3.0  # ~0.01 to ~0.5
    
    # Random rotation (quaternions)
    rotations = np.random.randn(num_points, 4)
    rotations = rotations / np.linalg.norm(rotations, axis=1, keepdims=True)
    
    # Build PLY header
    header = f"""ply
format binary_little_endian 1.0
element vertex {num_points}
property float x
property float y
property float z
property float nx
property float ny
property float nz
property float f_dc_0
property float f_dc_1
property float f_dc_2
property float opacity
property float scale_0
property float scale_1
property float scale_2
property float rot_0
property float rot_1
property float rot_2
property float rot_3
end_header
"""
    
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'wb') as f:
        f.write(header.encode('ascii'))
        
        for i in range(num_points):
            # Write vertex data
            data = struct.pack('<' + 'f' * 17,
                positions[i, 0], positions[i, 1], positions[i, 2],  # x, y, z
                0.0, 0.0, 0.0,  # nx, ny, nz
                colors[i, 0], colors[i, 1], colors[i, 2],  # f_dc_0, 1, 2
                opacity[i],  # opacity
                scales[i, 0], scales[i, 1], scales[i, 2],  # scale_0, 1, 2
                rotations[i, 0], rotations[i, 1], rotations[i, 2], rotations[i, 3]  # rot_0, 1, 2, 3
            )
            f.write(data)
    
    file_size = os.path.getsize(filepath)
    print(f"Created: {filepath}")
    print(f"  Points: {num_points}")
    print(f"  Size: {file_size / 1024:.1f} KB")
    
    return filepath

if __name__ == "__main__":
    print("=" * 50)
    print("Generating Sample 3DGS PLY Files")
    print("=" * 50)
    
    # Small test scene
    create_sample_ply("sample_cube_1k.ply", 1000)
    
    # Medium scene  
    create_sample_ply("sample_sphere_10k.ply", 10000)
    
    print("=" * 50)
    print("Sample files created in './scenes/' directory")
    print("These can be uploaded through the web interface")
    print("=" * 50)
