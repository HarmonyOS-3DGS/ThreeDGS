@echo off
chcp 65001 >nul 2>nul

copy /Y .env.local .env >nul 2>nul

set PYTHON_EXE=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXE=.venv\Scripts\python
) else (
    echo [tip] no venv, using system Python
    %PYTHON_EXE% -c "import fastapi; import celery" >nul 2>nul
    if errorlevel 1 (
        echo [err] missing fastapi/celery. run: pip install -r requirements.txt
        exit /b 1
    )
)

%PYTHON_EXE% run_local.py
