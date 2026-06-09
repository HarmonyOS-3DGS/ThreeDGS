"""Real HTTP integration test - API + Worker in same process."""

import os
import sys
import threading
import time
from pathlib import Path

# Env setup
os.environ["DATABASE_URL"] = "sqlite:///./realtest.db"
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
os.environ["USE_LOCAL_STORAGE"] = "true"
os.environ["LOCAL_STORAGE_DIR"] = "./realtest_storage"
os.environ["API_KEY"] = "test-key-123"

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PORT = 18002
URL = f"http://127.0.0.1:{PORT}"
KEY = "test-key-123"


def cleanup():
    import shutil

    for p in ["realtest.db", "realtest_storage", "realtest.db-journal"]:
        if os.path.exists(p):
            for _ in range(10):
                try:
                    shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
                    break
                except PermissionError:
                    time.sleep(0.3)


cleanup()

# Init DB
from backend.core.database import init_db  # noqa: E402

init_db()
print("[1/5] DB initialized")

# Start Celery worker thread (shares memory broker with API)
print("[2/5] Starting Celery worker thread")
from backend.worker.celery_app import app as celery_app  # noqa: E402

worker_running = True


def run_worker():
    # Start a worker that consumes from the in-memory broker
    with celery_app.connection():
        worker = celery_app.Worker(
            hostname="test_worker@localhost",
            pool="solo",
            concurrency=1,
            loglevel="warning",
            broker_connection_retry_on_startup=True,
        )
        worker.start()


worker_thread = threading.Thread(target=run_worker, daemon=True)
worker_thread.start()
time.sleep(2)
print("Worker thread started")

# Start API in background thread
print("[3/5] Starting API server")
import uvicorn  # noqa: E402

from backend.api.main import app as fastapi_app  # noqa: E402

api_running = True
api_server = None


def run_api():
    global api_server
    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=PORT, log_level="warning")
    api_server = uvicorn.Server(config)
    api_server.run()


api_thread = threading.Thread(target=run_api, daemon=True)
api_thread.start()

# Wait for API
import httpx  # noqa: E402

ready = False
for _ in range(30):
    try:
        r = httpx.get(f"{URL}/docs", timeout=1)
        if r.status_code == 200:
            ready = True
            break
    except Exception:
        pass
    time.sleep(0.5)

if not ready:
    print("API failed to start")
    sys.exit(1)
print("API ready on", URL)

# Tests
passed = 0
failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1


print("\n[4/5] Running real HTTP tests")

# Test 1: Create task
body = {
    "externalCode": "INT-TEST-001",
    "fileInfos": [{"fileName": "test.mp4", "sha256": "abc", "contentLength": 16, "fileUrl": ""}],
    "scene": "indoor",
}
r = httpx.post(
    f"{URL}/tasks",
    json=body,
    headers={"Authorization": KEY, "projectId": "proj-test"},
    timeout=10,
)
check("Create task", r.status_code == 200, f"status={r.status_code}")

if r.status_code != 200:
    print("ABORT - create task failed")
    sys.exit(1)

task_id = r.json()["taskId"]
print(f"  Task ID: {task_id}")

# Test 2: Start task
r = httpx.post(
    f"{URL}/tasks/{task_id}/start",
    headers={"Authorization": KEY, "projectId": "proj-test"},
    timeout=5,
)
check(
    "Start task", r.status_code == 200 and r.json()["ret"]["code"] == 0, f"status={r.status_code}"
)

# Test 3: Query task
r = httpx.get(
    f"{URL}/tasks/{task_id}",
    headers={"Authorization": KEY, "projectId": "proj-test"},
    timeout=5,
)
check(
    "Query task",
    r.status_code == 200 and r.json()["status"] == "processing",
    f"status={r.status_code}",
)

# Test 4: Wait for completion
print("\n  Waiting for pipeline completion (~15s)...")
status = ""
for i in range(40):
    r = httpx.get(
        f"{URL}/tasks/{task_id}",
        headers={"Authorization": KEY, "projectId": "proj-test"},
        timeout=5,
    )
    data = r.json()
    status = data["status"]
    print(
        f"    t={i + 1}s status={status:10} stage={data['currentStage']:15} progress={data['progress']:3}%"
    )
    if status in ("completed", "failed"):
        break
    time.sleep(1)

check("Pipeline completes", status == "completed", f"final={status}")

# Test 5: Final state
r = httpx.get(
    f"{URL}/tasks/{task_id}",
    headers={"Authorization": KEY, "projectId": "proj-test"},
    timeout=5,
)
data = r.json()
check("Final progress is 100%", data["progress"] == 100, f"progress={data['progress']}")

# Cleanup
print("\n[5/5] Cleanup")
if api_server:
    api_server.should_exit = True
api_thread.join(timeout=5)

# Give worker time to finish
time.sleep(1)

cleanup()

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
print(f"{'=' * 40}")
if failed == 0:
    print("All real integration tests passed!")
else:
    print(f"{failed} test(s) failed")

sys.exit(0 if failed == 0 else 1)
