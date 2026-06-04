#!/bin/bash

# 3D Gaussian Splatting Demo - Quick Start Script
# Usage: ./start.sh [backend|frontend|all]

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

color_green() { echo -e "\033[0;32m$1\033[0m"; }
color_blue() { echo -e "\033[0;34m$1\033[0m"; }
color_yellow() { echo -e "\033[1;33m$1\033[0m"; }

case "${1:-all}" in
  backend)
    color_blue "Starting 3DGS Demo Backend..."
    cd "$PROJECT_DIR/backend"
    
    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
      color_yellow "Creating Python virtual environment..."
      python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    # Install dependencies
    color_yellow "Installing Python dependencies..."
    pip install -q -r requirements.txt
    
    # Create scenes directory
    mkdir -p "$PROJECT_DIR/scenes"
    
    color_green "Backend starting at http://localhost:8000"
    color_green "API Docs: http://localhost:8000/docs"
    python main.py
    ;;
    
  frontend)
    color_blue "Starting 3DGS Demo Frontend..."
    cd "$PROJECT_DIR/frontend"
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
      color_yellow "Installing Node.js dependencies..."
      npm install
    fi
    
    color_green "Frontend starting at http://localhost:3000"
    npm run dev
    ;;
    
  all|*)
    color_blue "Starting 3DGS Demo - Full Stack"
    color_yellow "This will start both backend and frontend in separate processes."
    color_yellow "Press Ctrl+C to stop."
    
    # Start backend in background
    color_green "Starting backend..."
    cd "$PROJECT_DIR"
    ./start.sh backend &
    BACKEND_PID=$!
    
    # Wait for backend to be ready
    sleep 3
    
    # Start frontend
    color_green "Starting frontend..."
    cd "$PROJECT_DIR"
    ./start.sh frontend
    
    # Cleanup
    kill $BACKEND_PID 2>/dev/null || true
    ;;
esac
