#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# 加载本地配置
cp -f .env.local .env 2>/dev/null || true

# 选择 Python 解释器：优先 .venv，不可用时回退系统 Python
PYTHON_EXE="python3"
if [ -f ".venv/bin/python" ]; then
    PYTHON_EXE=".venv/bin/python"
else
    echo "[提示] 虚拟环境不存在，使用系统 Python3"
    $PYTHON_EXE -c "import fastapi, celery" 2>/dev/null || {
        echo "[错误] 系统 Python3 缺少 fastapi/celery，请先: pip install -r requirements.txt"
        exit 1
    }
fi

# 使用 Python 线程模式启动（API + Worker 同进程，memory broker 共享）
exec $PYTHON_EXE run_local.py
