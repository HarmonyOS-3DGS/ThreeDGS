"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routers import sse, tasks
from backend.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库。"""
    init_db()
    yield


app = FastAPI(title="3DGS Platform", version="3.0.0", lifespan=lifespan)

# CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由注册
app.include_router(tasks.router)
app.include_router(sse.router)

# 挂载静态文件（前端页面）
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
