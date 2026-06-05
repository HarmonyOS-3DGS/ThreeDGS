# 3DGS Platform — Agent 开发指南

> FastAPI + Celery + SQLAlchemy · 3D Gaussian Splatting 训练平台 · MVP 阶段
> 中文注释和文档。算法层为 Stub 空壳，15 秒走完流水线。

---

## 核心流程

```
POST /tasks (创建, 上传文件+元数据) → status=queued
POST /tasks/{id}/start (启动流水线) → status=processing, 提交 Celery 链
GET  /tasks/{id} (轮询状态/进度/输出文件) / SSE 实时推送
```

四阶段 Celery 链: `extract_frames → colmap_sfm → train_gs → compress`
各阶段通过 `prev_result: dict` 传递路径字段 (`task_id → frames_dir → colmap_dir → model_path → compressed_spz/sog`)

---

## 常用命令

```bash
# 环境配置 (Windows 需用代理)
$env:HTTP_PROXY="http://proxyhes-gy.security.huawei.com:8080"
pip install --proxy $env:HTTP_PROXY -r requirements.txt

# 初始化数据库 (先删除旧 DB 避免 schema 冲突)
Remove-Item -Force .\3dgs.db -ErrorAction SilentlyContinue
python -c "from backend.core.database import init_db; init_db()"

# 启动 (两个终端)
celery -A backend.worker.celery_app worker --loglevel=info -c 1 --pool=solo
uvicorn backend.api.main:app --reload --port 8000

# 测试
Remove-Item -Force .\test.db -ErrorAction SilentlyContinue
pytest -v                          # 单元测试 (23 个)
python scripts/real_test.py        # 端到端集成测试 (API+Worker 同进程)
```

---

## 关键架构约束

### 数据库

- **无 migration** — `init_db()` 直接 `Base.metadata.create_all()`
- 测试使用 `sqlite:///./test.db`，session 结束时 `drop_all` 清理
- Python 文件内用 `SessionLocal()` 手动创建 session，`try/finally` 确保关闭

### Celery 任务更新模式

Worker 中每个任务文件有 `_update_task()` 辅助函数，直接操作 DB：
```python
def _update_task(task_id: str, stage: str, progress: int):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.current_stage = stage
            task.progress = progress
            db.commit()
    finally:
        db.close()
```
`self.update_state()` 用 `try/except` 包裹，避免测试环境无 Celery 上下文时崩溃。

### 存储

`backend/core/storage.py` — 懒加载代理，通过 `USE_LOCAL_STORAGE` 环境变量在 MinIO/Local 之间切换。

### 鉴权

`X-API-Key` Header · `.env` 中 `API_KEY` 留空关闭鉴权 · 默认开发 Key: `3dgs-dev-2026`

### pytest.ini

`testpaths = tests`，`norecursedirs = scripts reference ...` — 确保 `scripts/` 下的集成脚本不会被 pytest 扫描。

---

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks` | 创建任务 (Form: `external_code` + `files_meta` JSON + UploadFile) |
| POST | `/tasks/{id}/start` | 启动流水线 (status: queued→processing) |
| GET | `/tasks/{id}` | 查询状态/进度/输出文件 |
| GET | `/tasks/{id}/events` | SSE 实时进度 (每 2s) |

旧的 `/upload`、`/projects` 已废弃，返回 410。

---

## 数据模型

`backend/core/database.py`:

| 模型 | 关键字段 |
|------|---------|
| `Task` | id(UUID), external_code, status(queued/processing/completed/failed), current_stage, progress, remaining_time |
| `TaskFile` | id, task_id(FK), original_filename, sha256, file_size, file_path |

**状态映射**: `TaskStatus` 对外暴露 → `TaskStage` 内部阶段
| 外部 | 内部 |
|------|------|
| queued | pending |
| processing | extracting → colmap → training → compressing |
| completed | completed |
| failed | failed |

---

## Stub 模型

| 文件 | 类/方法 | 未来替换 |
|------|--------|---------|
| `worker/models/preprocessor.py` | `Preprocessor.extract_frames()` / `run_colmap()` | FFmpeg + COLMAP CLI |
| `worker/models/trainer.py` | `Trainer.train()` | gsplat / Nerfstudio |
| `worker/models/compressor.py` | `Compressor.compress_ply_to_spz/sog()` | 3dgsconverter |

Worker 任务接口签名 (输入/输出 dict) 保持不变，替换模型无需修改 Celery 链。

---

## 前端

- 纯 HTML/CSS/JS，FastAPI `StaticFiles` 挂载 `/` 目录
- `app.js` 硬编码 `API_KEY = "3dgs-dev-2026"`，与 `.env.local` 一致
- `viewer.js` 通过 SSE 连接 `/tasks/{id}/events` 实时更新进度
