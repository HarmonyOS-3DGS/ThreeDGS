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

# 使用 Python 线程模式启动（API + Worker 同进程，memory broker 共享）
exec .venv/bin/python run_local.py
