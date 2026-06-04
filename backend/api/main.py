"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.core.database import init_db
from backend.api.routers import upload, projects, sse

app = FastAPI(title="3DGS Platform", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def on_startup():
    init_db()

# API routes
app.include_router(upload.router)
app.include_router(projects.router)
app.include_router(sse.router)

# Static files (frontend)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
