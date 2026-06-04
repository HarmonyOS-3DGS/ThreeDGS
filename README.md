# 3D Gaussian Splatting 工程化平台

> 基于 FastAPI + Celery + SQLAlchemy 的 3DGS 端到端训练平台（MVP 阶段）。
> 训练模型为 Stub 实现，不关注具体算法，专注工程架构与前后端衔接。

---

## 架构概览

### 生产模式（Docker）
```
用户浏览器 → FastAPI (上传/查询/SSE)
                ↓
        PostgreSQL (元数据)    Redis (Celery 队列)
                ↓                        ↓
        Celery Worker ←───────────────┘
        ├── extract_frames (stub)
        ├── colmap_sfm (stub)
        ├── train_gs (stub)
        └── compress (stub)
                ↓
        MinIO (对象存储)
```

### 本地轻量模式（无 Docker）
```
用户浏览器 → FastAPI
                ↓
        SQLite (本地文件)      内存 Celery (无需 Redis)
                ↓                        ↓
        Celery Worker
                ↓
        本地文件系统 (替代 MinIO)
```

---

## 快速启动

### 方式一：一键本地启动（推荐，无需 Docker）

```bash
# Windows
run_local.bat

# Linux / Mac
bash run_local.sh
```

访问：
- **上传页面**: http://localhost:8000/index.html
- **任务列表**: http://localhost:8000/status.html
- **API 文档**: http://localhost:8000/docs

> 本地模式使用 SQLite + 内存 Celery + 本地文件存储，零外部依赖。

### 方式二：Docker Compose

```bash
# 启动全部服务
docker-compose up --build -d

# 查看服务状态
docker-compose ps
```

### 方式三：手动分步启动

```bash
# 1. 创建虚拟环境
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 选择配置
cp .env.local .env          # 本地轻量模式（无需 Docker）
# 或
cp .env.example .env       # 生产模式（需 PostgreSQL + Redis + MinIO）

# 4. 初始化数据库
python -c "from backend.core.database import init_db; init_db()"

# 5. 启动 Worker（新开终端）
celery -A backend.worker.celery_app worker --loglevel=info -c 1 --pool=solo

# 6. 启动 API
uvicorn backend.api.main:app --reload --port 8000
```

---

## 项目结构

```
.
├── backend/
│   ├── api/                    # FastAPI 路由和 Schema
│   │   ├── routers/
│   │   │   ├── upload.py       # POST /upload
│   │   │   ├── projects.py     # GET /projects /projects/{id}
│   │   │   └── sse.py          # SSE 实时进度
│   │   └── schemas/
│   ├── worker/                 # Celery 任务和模型 Stub
│   │   ├── tasks/              # 4阶段流水线任务
│   │   └── models/             # 空壳模型层
│   └── core/                   # 配置、数据库、存储、鉴权
├── frontend/                   # 静态前端页面
├── tests/                      # pytest 测试套件（21个测试）
├── scripts/                    # 集成测试脚本
├── docker-compose.yml          # 六服务容器编排
├── run_local.bat / run_local.sh # 一键启动脚本
├── .env.local                  # 本地轻量配置
└── requirements.txt
```

---

## API 端点

所有接口需要 `X-API-Key` Header（默认: `3dgs-dev-2026`）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/upload` | 上传视频/图片，启动训练流水线 |
| GET | `/projects` | 列出所有项目 |
| GET | `/projects/{id}` | 查询单个项目状态 |
| GET | `/projects/{id}/events` | SSE 实时进度推送 |

### 鉴权

通过 `.env` 中的 `API_KEY` 配置：
- 留空 → 关闭鉴权（开放访问）
- 设置值 → 所有请求需带 `X-API-Key: <key>`

---

## 测试

```bash
# 运行全部单元测试
pytest -v

# 带覆盖率
pytest --cov=backend --cov-report=term-missing

# 真实端到端集成测试（启动真实 API + Worker，发送 HTTP 请求）
python scripts/real_test.py
```

---

## 流水线阶段

| 阶段 | 状态 | 说明 | Stub 耗时 |
|------|------|------|----------|
| 帧提取 | `extracting` | FFmpeg 帧提取（stub） | ~2s |
| COLMAP | `colmap` | SfM 位姿估计（stub） | ~3s |
| 训练 | `training` | 3DGS 训练（stub） | ~7s |
| 压缩 | `compressing` | 格式转换压缩（stub） | ~3s |
| 完成 | `completed` | 生成 SPZ/SOG 文件 | - |

**Stub 模式下总耗时约 15 秒**。

---

## 技术选型

| 层级 | 生产方案 | 本地轻量方案 |
|------|---------|-------------|
| 后端框架 | FastAPI + Pydantic | FastAPI + Pydantic |
| 任务队列 | Celery + Redis | Celery + 内存 broker |
| 数据库 | PostgreSQL + SQLAlchemy | SQLite + SQLAlchemy |
| 对象存储 | MinIO | 本地文件系统 |
| 鉴权 | API Key (X-API-Key) | API Key (X-API-Key) |
| 前端 | 原生 HTML/JS | 原生 HTML/JS |
| 容器化 | Docker Compose | 无需 Docker |
| 测试 | pytest + httpx | pytest + httpx |
