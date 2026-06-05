"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.core.database import init_db
from backend.api.routers import tasks, sse

app = FastAPI(title="3DGS Platform", version="3.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def on_startup():
    init_db()

# API routes
app.include_router(tasks.router)
app.include_router(sse.router)

# Static files (frontend)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
