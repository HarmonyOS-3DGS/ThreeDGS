#!/bin/sh
set -e

# 确保变量存在（允许空值）
export FRONTEND_API_BASE="${FRONTEND_API_BASE:-}"

# 非空时校验 scheme 并去掉尾部斜杠
if [ -n "$FRONTEND_API_BASE" ]; then
    case "$FRONTEND_API_BASE" in
        http://*|https://*) ;;
        *) echo "ERROR: FRONTEND_API_BASE must start with http:// or https:// (got: $FRONTEND_API_BASE)" >&2; exit 1 ;;
    esac
    # 去掉尾部斜杠，避免拼接出 /tasks 时出现双斜杠
    FRONTEND_API_BASE="${FRONTEND_API_BASE%/}"
fi

# 替换模板中的 ${FRONTEND_API_BASE}，nginx 自身的 $host/$remote_addr 等不受影响
envsubst '${FRONTEND_API_BASE}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

exec "$@"
