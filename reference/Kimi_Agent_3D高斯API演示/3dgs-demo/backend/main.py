"""
3D Gaussian Splatting Demo API - Main Application Entry Point.

A FastAPI-based service providing:
- JWT-based authentication and user management
- 3D Gaussian Splatting scene upload, management, and download
- PLY/SPLAT/KSPLAT file format support with metadata extraction
- Web viewer integration endpoints
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

from config import get_settings
from database import init_db
from routers import auth, scenes, system

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - initialize on startup."""
    # Startup
    print("=" * 60)
    print("3D Gaussian Splatting Demo API Starting...")
    print("=" * 60)
    init_db()
    print("Database initialized.")
    print(f"Scenes storage directory: {settings.SCENES_DIR}")
    print(f"Demo mode: {settings.DEMO_MODE}")
    print("=" * 60)
    yield
    # Shutdown
    print("Shutting down 3DGS Demo API...")


# Create FastAPI application
app = FastAPI(
    title="3D Gaussian Splatting Demo API",
    description="""
    API service for 3D Gaussian Splatting scene management.
    
    ## Features
    
    - **Authentication**: JWT-based auth with user registration/login
    - **Scene Management**: Upload, download, and manage 3DGS scenes
    - **File Support**: PLY, SPLAT, KSPLAT formats
    - **Metadata Extraction**: Automatic Gaussian count, SH detection, scale estimation
    - **Web Viewer**: Direct file serving for browser-based 3DGS viewers
    
    ## Authentication
    
    All protected endpoints require a Bearer token in the Authorization header:
    ```
    Authorization: Bearer <your-jwt-token>
    ```
    
    Obtain a token by calling `/api/v1/auth/login` with valid credentials.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware - allow frontend to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions gracefully."""
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )


# Include routers with versioned prefix
app.include_router(auth.router, prefix="/api/v1")
app.include_router(scenes.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")


@app.get("/")
def root():
    """API root - redirect to docs."""
    return {
        "message": "3D Gaussian Splatting Demo API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/system/health"
    }


@app.get("/api/v1")
def api_root():
    """API v1 root."""
    return {
        "version": "1.0.0",
        "endpoints": {
            "auth": "/api/v1/auth",
            "scenes": "/api/v1/scenes",
            "system": "/api/v1/system",
        }
    }


# Run the application (for direct execution)
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
