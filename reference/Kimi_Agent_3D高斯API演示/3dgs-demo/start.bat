@echo off
REM 3D Gaussian Splatting Demo - Quick Start Script for Windows
REM Usage: start.bat [backend|frontend|all]

set PROJECT_DIR=%~dp0

if "%~1"=="backend" goto backend
if "%~1"=="frontend" goto frontend
goto all

:backend
echo [32mStarting 3DGS Demo Backend...[0m
cd /d "%PROJECT_DIR%\backend"

if not exist "venv" (
  echo [33mCreating Python virtual environment...[0m
  python -m venv venv
)

call venv\Scripts\activate.bat

echo [33mInstalling Python dependencies...[0m
pip install -q -r requirements.txt

if not exist "%PROJECT_DIR%\scenes" mkdir "%PROJECT_DIR%\scenes"

echo [32mBackend starting at http://localhost:8000[0m
echo [32mAPI Docs: http://localhost:8000/docs[0m
python main.py
goto end

:frontend
echo [32mStarting 3DGS Demo Frontend...[0m
cd /d "%PROJECT_DIR%\frontend"

if not exist "node_modules" (
  echo [33mInstalling Node.js dependencies...[0m
  npm install
)

echo [32mFrontend starting at http://localhost:3000[0m
npm run dev
goto end

:all
echo [32mStarting 3DGS Demo - Full Stack[0m
echo [33mPlease start backend and frontend in separate terminals:[0m
echo   Terminal 1: start.bat backend
echo   Terminal 2: start.bat frontend
goto end

:end
