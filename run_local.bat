@echo off
chcp 65001 >nul

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先创建：
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

REM 加载本地配置
copy /Y .env.local .env >nul 2>nul

REM 使用 Python 线程模式启动（API + Worker 同进程，memory broker 共享）
.venv\Scripts\python run_local.py
