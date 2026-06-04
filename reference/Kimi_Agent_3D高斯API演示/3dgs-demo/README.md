# 3D Gaussian Splatting Demo - Full Stack Implementation

A complete **FastAPI backend + React frontend** demonstration of 3D Gaussian Splatting (3DGS) scene management with JWT authentication, web-based 3D visualization, and PLY/SPLAT/KSPLAT file support.

---

## Architecture Overview

```
3dgs-demo/
├── backend/              # FastAPI Python backend
│   ├── main.py           # Application entry point
│   ├── config.py         # Configuration management
│   ├── database.py       # SQLAlchemy ORM setup
│   ├── models.py         # Database models (User, Scene)
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── auth.py           # JWT authentication & password hashing
│   ├── scene_manager.py  # 3DGS file management & metadata extraction
│   ├── routers/          # API route handlers
│   │   ├── auth.py       # Authentication endpoints
│   │   ├── scenes.py     # Scene CRUD endpoints
│   │   └── system.py     # System info & health check
│   └── requirements.txt  # Python dependencies
├── frontend/             # React TypeScript frontend
│   ├── src/
│   │   ├── main.tsx      # React entry point
│   │   ├── App.tsx       # Router & route configuration
│   │   ├── api.ts        # API client (axios)
│   │   ├── types.ts      # TypeScript type definitions
│   │   ├── hooks/
│   │   │   └── useAuth.tsx   # Authentication context hook
│   │   └── pages/
│   │       ├── LoginPage.tsx      # User login
│   │       ├── RegisterPage.tsx   # User registration
│   │       ├── DashboardPage.tsx  # Scene management dashboard
│   │       └── ViewerPage.tsx     # 3DGS web viewer
│   ├── package.json
│   └── vite.config.ts
├── scenes/               # Uploaded 3DGS scene storage
└── README.md
```

---

## Technology Stack

### Backend
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web Framework | **FastAPI** | High-performance API framework with auto OpenAPI docs |
| Database | **SQLite + SQLAlchemy** | User and scene metadata storage |
| Authentication | **JWT + OAuth2** | Stateless token-based auth with Argon2 password hashing |
| File Handling | **Python Multipart** | PLY/SPLAT/KSPLAT upload and download |
| Metadata Extraction | **Binary PLY Parser** | Gaussian count, SH detection, scale estimation |
| Server | **Uvicorn** | ASGI server with hot reload |

### Frontend
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | **React 18 + TypeScript** | Component-based UI with type safety |
| Router | **React Router v6** | Client-side routing |
| Build Tool | **Vite** | Fast development and optimized builds |
| 3D Rendering | **Three.js + @mkkellogg/gaussian-splats-3d** | Browser-based 3DGS scene rendering |
| HTTP Client | **Axios** | API communication with interceptors |
| Styling | **Inline CSS** | Component-scoped dark theme styling |

---

## Features

### Authentication System
- **User Registration** with username, email, password (Argon2 hashed)
- **JWT Login** with OAuth2 password flow
- **Token-based API Protection** via Authorization: Bearer header
- **Automatic Token Management** with localStorage persistence
- **Role-based Access Control** (user/admin roles)

### 3DGS Scene Management
- **Multi-format Support**: PLY, SPLAT, KSPLAT files
- **Metadata Extraction**: Automatic Gaussian count, spherical harmonics detection, scene scale estimation
- **File Upload/Download**: Chunked multipart upload with size validation (500MB max)
- **Public/Private Scenes**: Access control for scene visibility
- **View Counting**: Track scene popularity

### Web 3D Viewer
- **Interactive Rendering**: Orbit, pan, zoom controls
- **Format Support**: PLY and SPLAT file rendering via GaussianSplats3D
- **GPU Acceleration**: WebGL-based with SIMD-optimized splat sorting
- **Fallback Mode**: Scene info display when WebGL unavailable

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Start Backend

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Start server
python main.py
```

Backend runs at `http://localhost:8000`

- API Documentation: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 2. Start Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend runs at `http://localhost:3000`

### 3. Access the Application

1. Open `http://localhost:3000`
2. Register a new account or login
3. Upload 3DGS scenes (.ply files)
4. View scenes in the interactive 3D viewer

---

## API Endpoints

### Authentication
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/v1/auth/register` | Create new user account | No |
| POST | `/api/v1/auth/login` | Login and get JWT token | No |
| GET | `/api/v1/auth/me` | Get current user info | Yes |

### Scene Management
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/scenes` | List scenes (public + mine) | Optional |
| POST | `/api/v1/scenes` | Upload new scene | Yes |
| GET | `/api/v1/scenes/{id}` | Get scene details | Optional* |
| PUT | `/api/v1/scenes/{id}` | Update scene metadata | Yes |
| DELETE | `/api/v1/scenes/{id}` | Delete scene | Yes |
| GET | `/api/v1/scenes/{id}/download` | Download scene file | Optional* |
| GET | `/api/v1/scenes/{id}/raw` | Get scene file (for viewer) | Optional* |

*Optional: Public scenes accessible without auth, private scenes require ownership.

### System
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/system/info` | System information | No |
| GET | `/api/v1/system/health` | Health check | No |
| GET | `/api/v1/system/stats` | Usage statistics | Yes |

---

## Database Schema

### Users Table
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | User ID |
| username | VARCHAR(50) | Unique username |
| email | VARCHAR(100) | Unique email |
| full_name | VARCHAR(100) | Display name |
| hashed_password | VARCHAR(255) | Argon2 password hash |
| role | VARCHAR(20) | user/admin |
| is_active | BOOLEAN | Account status |
| created_at | DATETIME | Registration time |

### Scenes Table
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Scene ID |
| name | VARCHAR(100) | Scene name |
| description | TEXT | Scene description |
| filename | VARCHAR(255) | Original filename |
| file_path | VARCHAR(500) | Storage path |
| file_size | INTEGER | File size in bytes |
| file_format | VARCHAR(10) | ply/splat/ksplat |
| num_gaussians | INTEGER | Gaussian count from PLY |
| scene_scale | FLOAT | Estimated scene scale |
| has_sh | BOOLEAN | Has spherical harmonics |
| sh_degree | INTEGER | SH degree (0-3) |
| status | VARCHAR(20) | ready/processing/error |
| owner_id | INTEGER FK | Owner user ID |
| is_public | BOOLEAN | Visibility flag |
| view_count | INTEGER | View counter |
| created_at | DATETIME | Upload time |

---

## PLY File Format Support

The system extracts metadata from 3D Gaussian Splatting PLY files:

### Detected Properties
- **Vertex Count**: Number of 3D Gaussians in the scene
- **Spherical Harmonics**: Detection of `f_dc_*` and `f_rest_*` properties
- **SH Degree**: Auto-calculated from coefficient count (1/4/9 = degree 0/1/2/3)
- **Scene Scale**: Estimated from position data bounding box diagonal

### Supported Properties
| Property | Description |
|----------|-------------|
| x, y, z | Gaussian center position |
| nx, ny, nz | Normal vector |
| f_dc_* | DC spherical harmonic coefficients |
| f_rest_* | Higher-order SH coefficients |
| opacity | Alpha transparency |
| scale_* | Scaling factors |
| rot_* | Rotation quaternion |

---

## 3DGS Training Pipeline (Integration Guide)

While this demo focuses on **scene management and visualization**, here's how to integrate training:

### Option 1: gsplat (Recommended)
```bash
# Install gsplat
pip install gsplat

# Train on COLMAP dataset
python -m gsplat.examples.simple_trainer default \
    --data_dir /path/to/colmap/data \
    --data_factor 4 \
    --result_dir ./results

# Export PLY file (upload to this system)
```

### Option 2: Nerfstudio Splatfacto
```bash
# Install nerfstudio
pip install nerfstudio

# Process images and train
ns-process-data images --data /path/to/images --output-dir ./processed
ns-train splatfacto --data ./processed

# Export Gaussian Splat
ns-export gaussian-splat --load-config ./outputs/config.yml
```

### Option 3: Docker (Production)
```bash
docker run --gpus all \
  -v $(pwd)/data:/data \
  -p 7007:7007 \
  ghcr.io/nerfstudio-project/nerfstudio:latest \
  ns-train splatfacto --data /data
```

---

## Configuration

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (built-in) | JWT signing secret |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 1440 | Token expiry (24h) |
| `DATABASE_URL` | sqlite:///./3dgs_demo.db | Database connection |
| `SCENES_DIR` | ./scenes | Scene file storage path |
| `MAX_UPLOAD_SIZE` | 524288000 (500MB) | Max upload size in bytes |
| `DEMO_MODE` | True | Demo mode flag |

Create a `.env` file in the `backend/` directory to override defaults.

---

## Security Considerations

| Feature | Implementation |
|---------|---------------|
| Password Hashing | Argon2 (OWASP recommended) |
| Token Signing | HS256 JWT with secret key |
| Token Storage | HttpOnly cookie recommended for production |
| CORS | Configurable allowed origins |
| File Validation | Extension whitelist, size limits |
| Access Control | Owner-based + public/private scenes |

---

## Production Deployment

### Backend
```bash
# Use production ASGI server
pip install gunicorn

gunicorn main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Frontend
```bash
npm run build
# Serve dist/ folder with nginx or static file server
```

### Docker (Full Stack)
```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./scenes:/app/scenes
    environment:
      - SECRET_KEY=${SECRET_KEY}
  
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
```

---

## References

- [3D Gaussian Splatting Paper (Kerbl et al., 2023)](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/)
- [gsplat Library](https://github.com/nerfstudio-project/gsplat)
- [Nerfstudio Documentation](https://docs.nerf.studio/)
- [GaussianSplats3D Web Viewer](https://github.com/mkkellogg/GaussianSplats3D)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
