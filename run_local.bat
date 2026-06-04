@echo off
chcp 65001 >nul
echo ========================================
echo  3DGS Platform - 本地轻量启动
echo ========================================

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检查虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先创建：
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

:: 加载本地配置
copy /Y .env.local .env >nul 2>&1

:: 创建本地存储目录
if not exist "local_storage" mkdir local_storage

:: 创建上传临时目录
if not exist "uploads" mkdir uploads

echo.
echo [1/3] 初始化数据库...
.venv\Scripts\python.exe -c "from backend.core.database import init_db; init_db(); print('  数据库初始化完成')"

echo.
echo [2/3] 启动 Celery Worker...
start "3DGS Worker" cmd /k ".venv\Scripts\celery.exe -A backend.worker.celery_app worker --loglevel=info -c 1 --pool=solo"

timeout /t 2 /nobreak >nul

echo.
echo [3/3] 启动 FastAPI 服务...
echo.
echo ========================================
echo  服务已启动！访问地址：
echo   - 前端页面: http://localhost:8000/index.html
echo   - API 文档: http://localhost:8000/docs
echo   - 任务列表: http://localhost:8000/status.html
echo ========================================
echo.
echo 按 Ctrl+C 停止服务，关闭 Worker 窗口停止 Worker
echo.
.venv\Scripts\uvicorn.exe backend.api.main:app --host 0.0.0.0 --port 8000 --reload
