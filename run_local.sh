#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ ! -f ".venv/bin/python" ]; then
    echo "[错误] 虚拟环境不存在，请先创建："
    echo "  python3 -m venv .venv"
    echo "  .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# 加载本地配置
cp -f .env.local .env 2>/dev/null || true

# 创建本地存储目录
mkdir -p local_storage uploads

echo "[1/3] 初始化数据库..."
.venv/bin/python -c "from backend.core.database import init_db; init_db(); print('  数据库初始化完成')"

echo "[2/3] 启动 Celery Worker..."
.venv/bin/celery -A backend.worker.celery_app worker --loglevel=info -c 1 --pool=solo &
WORKER_PID=$!
sleep 2

echo "[3/3] 启动 FastAPI 服务..."
echo "========================================"
echo " 服务已启动！访问地址："
echo "  - 前端页面: http://localhost:8000/index.html"
echo "  API 文档: http://localhost:8000/docs"
echo "  任务列表: http://localhost:8000/status.html"
echo "========================================"
echo "按 Ctrl+C 停止服务"

.venv/bin/uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload

# 清理 Worker
echo "停止 Worker..."
kill $WORKER_PID 2>/dev/null || true
