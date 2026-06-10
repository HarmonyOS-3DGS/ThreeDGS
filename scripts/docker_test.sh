#!/usr/bin/env bash
# 3DGS 平台 Docker 端到端测试
# 用法: docker-compose up --build -d && bash scripts/docker_test.sh
set -e

# auto-detect python
PYTHON=$(command -v python3 || command -v python || echo "python3")

HOST="${HOST:-http://localhost:8000}"
KEY="${AUTH_KEY:-}"
HEADER_AUTH=()
if [ -n "$KEY" ]; then
  HEADER_AUTH=(-H "Authorization: $KEY")
fi

PID="docker-test"
TASK_ID=""
PASS=0
FAIL=0

check() {
  local name="$1" code="$2" detail="$3"
  if [ "$code" -ge 200 ] && [ "$code" -lt 300 ]; then
    echo "  [PASS] $name"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $name (HTTP $code $detail)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== 3DGS Docker E2E Test ==="
echo "Target: $HOST"

# 1. 创建任务
echo -e "\n[1/6] 创建任务..."
RESP=$(curl -s -w "\n%{http_code}" "$HOST/tasks" \
  -H "Content-Type: application/json" \
  -H "projectId: $PID" \
  "${HEADER_AUTH[@]}" \
  -d '{"externalCode":"E2E-TEST","fileInfos":[{"fileName":"test.mp4","sha256":"","contentLength":0,"fileUrl":"","fileRole":"source_video","mimeType":"video/mp4"}],"scene":"indoor"}')
HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | sed '$d')
check "Create task" "$HTTP_CODE"
TASK_ID=$(echo "$BODY" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['taskId'])" 2>/dev/null || true)
echo "  Task ID: $TASK_ID"

if [ -z "$TASK_ID" ] || [ "$HTTP_CODE" -ge 400 ]; then
  echo "ABORT: 创建任务失败"
  exit 1
fi

# 2. 获取上传 URL
echo -e "\n[2/6] 获取上传 URL..."
UPLOAD_URL=$(echo "$BODY" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['uploadInfos'][0]['url'])" 2>/dev/null)
UPLOAD_METHOD=$(echo "$BODY" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['uploadInfos'][0]['method'])" 2>/dev/null)
check "Upload URL exists" "$([ -n "$UPLOAD_URL" ] && echo 200 || echo 400)"
echo "  URL: $UPLOAD_URL"

# 3. 上传文件
echo -e "\n[3/6] 上传文件..."
# 生成一个 dummy 视频文件用于测试
TEST_FILE="/tmp/e2e_test_video.mp4"
echo "dummy_video_test_data" > "$TEST_FILE"

# 如果 URL 是相对路径 (本地模式), 拼上 HOST
UPLOAD_FULL_URL="$UPLOAD_URL"
if echo "$UPLOAD_URL" | grep -q "^/"; then
  UPLOAD_FULL_URL="${HOST}${UPLOAD_URL}"
fi

# 提取 headers 中的 Authorization
AUTH_HDR=$(echo "$BODY" | $PYTHON -c "import sys,json; h=json.load(sys.stdin)['uploadInfos'][0].get('headers',{}); print(h.get('Authorization',''))" 2>/dev/null)

UPLOAD_ARGS=(-s -w "\n%{http_code}" --upload-file "$TEST_FILE")
if [ -n "$AUTH_HDR" ]; then
  UPLOAD_ARGS+=(-H "Authorization: $AUTH_HDR")
fi
UPLOAD_RESP=$(curl "${UPLOAD_ARGS[@]}" "$UPLOAD_FULL_URL")
UPLOAD_CODE=$(echo "$UPLOAD_RESP" | tail -1)
check "Upload file" "$UPLOAD_CODE" "$(echo "$UPLOAD_RESP" | sed '$d')"

# 4. 启动任务
echo -e "\n[4/6] 启动任务..."
START_RESP=$(curl -s -w "\n%{http_code}" -X POST "$HOST/tasks/$TASK_ID/start" \
  -H "projectId: $PID" "${HEADER_AUTH[@]}")
START_CODE=$(echo "$START_RESP" | tail -1)
check "Start task" "$START_CODE"

# 5. 等待完成
echo -e "\n[5/6] 等待流水线完成 (~15s)..."
for i in $(seq 1 40); do
  QUERY=$(curl -s "$HOST/tasks/$TASK_ID" -H "projectId: $PID" "${HEADER_AUTH[@]}")
  STATUS=$(echo "$QUERY" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown")
  STAGE=$(echo "$QUERY" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['currentStage'])" 2>/dev/null || echo "?")
  PROG=$(echo "$QUERY" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['progress'])" 2>/dev/null || echo "0")
  printf "  t=%ds status=%-10s stage=%-15s progress=%3s%%\n" "$i" "$STATUS" "$STAGE" "$PROG"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 1
done
check "Pipeline completes" "$([ "$STATUS" = "completed" ] && echo 200 || echo 400)" "final=$STATUS"

# 6. 下载输出文件
echo -e "\n[6/6] 下载输出文件..."
DOWNLOAD_URL=$(echo "$QUERY" | $PYTHON -c "import sys,json; d=json.load(sys.stdin)['downloadInfos']; print(d[0]['url'] if d else '')" 2>/dev/null)
if [ -n "$DOWNLOAD_URL" ]; then
  DL_FULL_URL="$DOWNLOAD_URL"
  if echo "$DOWNLOAD_URL" | grep -q "^/"; then
    DL_FULL_URL="${HOST}${DOWNLOAD_URL}"
  fi
  DL_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$DL_FULL_URL")
  check "Download SPZ/SOG" "$DL_CODE"
else
  check "Download SPZ/SOG" 404 "no downloadInfos"
fi

echo -e "\n========================================"
echo "Results: $PASS passed, $FAIL failed"
echo "========================================"
[ "$FAIL" -eq 0 ] && echo "All Docker tests passed!" || echo "$FAIL test(s) failed"
[ "$FAIL" -eq 0 ]
