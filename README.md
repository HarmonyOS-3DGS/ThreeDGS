# 3D Gaussian Splatting 工程化平台

> 基于 FastAPI + Celery + SQLAlchemy 的 3DGS 端到端训练平台（MVP 阶段）。
> 训练模型为 Stub 实现，完整流水线约 15 秒。

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
用户浏览器 → FastAPI (创建任务 / 启动 / 查询 / SSE)
                ↓
        SQLite (本地文件)      内存 Celery (无需 Redis)
                ↓                        ↓
        Celery Worker (4阶段链)
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
- **查看器**: http://localhost:8000/viewer.html?id={task_id}
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

# 5. 启动（二选一）
# 方式 A：同进程线程模式（memory broker 共享，推荐）
python run_local.py

# 方式 B：分进程启动（需 Redis 等跨进程共享 broker）
#   修改 .env：CELERY_BROKER_URL=redis://localhost:6379/0
#   redis-server &
#   celery -A backend.worker.celery_app worker --loglevel=info -c 1 --pool=solo
#   uvicorn backend.api.main:app --reload --port 8000
```

---

## 项目结构

```
.
├── backend/
│   ├── api/                    # FastAPI 路由和 Schema
│   │   ├── routers/
│   │   │   ├── tasks.py        # POST /tasks, POST /{id}/start, GET /{id}
│   │   │   └── sse.py          # SSE 实时进度
│   │   └── schemas/
│   │       └── task.py         # Task 相关 Pydantic 模型
│   ├── worker/                 # Celery 任务和模型 Stub
│   │   ├── tasks/              # 4阶段流水线任务
│   │   └── models/             # 空壳模型层
│   └── core/                   # 配置、数据库、存储、鉴权
├── frontend/                   # 静态前端页面
├── tests/                      # pytest 测试套件（114+个测试）
├── scripts/                    # 集成测试脚本
├── docker-compose.yml          # 五服务容器编排
├── run_local.bat / run_local.sh # 一键启动脚本
├── .env.local                  # 本地轻量配置
└── requirements.txt
```

---

## API 端点

所有接口需要 `Authorization: Bearer <JWT>` Header。还需 `projectId` Header。
JWT 通过 `POST /auth/token` 用 `client_id:secret`（Basic Auth）换取。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/token` | 用 Basic Auth 换取 JWT access_token |
| POST | `/tasks` | 创建任务（JSON body），返回预签名上传 URL |
| PUT | `/tasks/{id}/upload/{filename}` | 本地上传文件 |
| POST | `/tasks/{id}/start` | 启动任务流水线 |
| GET | `/tasks/{id}` | 查询任务状态及输出文件下载链接 |
| GET | `/tasks/{id}/download/{filename}` | 下载输出文件（支持 Query 传 JWT） |
| GET | `/tasks/{id}/events` | SSE 实时进度推送（支持 Query 传 JWT） |

### 鉴权

通过 `.env` 中的 `SERVICE_ACCOUNTS` 和 `JWT_SECRET_KEY` 配置：
- `SERVICE_ACCOUNTS` 为空 → 关闭鉴权（开放访问）
- `SERVICE_ACCOUNTS=partner-a:sk-xxx,partner-b:sk-yyy` → 启用 JWT 鉴权
- `JWT_SECRET_KEY` 为 JWT 签名密钥，启用鉴权时必须配置强随机串

### 请求示例

```bash
# 0. 获取 JWT（client_id:secret 需在 SERVICE_ACCOUNTS 白名单中）
curl -X POST http://localhost:8000/auth/token \
  -H "Authorization: Basic $(echo -n 'partner-a:sk-xxx' | base64)"

# 返回 {"access_token": "eyJ...", "token_type": "bearer", "expires_in": 3600}

# 1. 创建任务
curl -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer eyJ..." \
  -H "projectId: proj-01" \
  -H "Content-Type: application/json" \
  -d '{"externalCode":"EXT-001","fileInfos":[{"fileName":"test.mp4","sha256":"abc","contentLength":16,"fileUrl":""}],"scene":"indoor"}'

# 2. 启动任务
curl -X POST http://localhost:8000/tasks/{task_id}/start \
  -H "Authorization: Bearer eyJ..." \
  -H "projectId: proj-01"

# 3. 查询任务
curl http://localhost:8000/tasks/{task_id} \
  -H "Authorization: Bearer eyJ..." \
  -H "projectId: proj-01"
```

---

## 测试

```bash
# 运行全部单元测试
pytest -v

# 带覆盖率
pytest --cov=backend --cov-report=term-missing

# 代码格式化与规范检查
ruff format .
ruff check .

# 真实端到端集成测试（启动真实 API + Worker，发送 HTTP 请求）
python scripts/real_test.py

# Docker 端到端测试（需先 docker compose up -d）
bash scripts/docker_test.sh
```

---

## 流水线阶段

### 外部状态机

| 状态 | 说明 |
|------|------|
| `pending` | 任务已创建，等待启动 |
| `processing` | 流水线正在执行 |
| `completed` | 全部阶段执行成功 |
| `failed` | 流水线执行出错 |

### 内部阶段

| 阶段 | 状态值 | 说明 | Stub 耗时 |
|------|--------|------|----------|
| 帧提取 | `extracting` | FFmpeg 帧提取（stub） | ~2s |
| COLMAP | `colmap` | SfM 位姿估计（stub） | ~3s |
| 训练 | `training` | 3DGS 训练（stub） | ~7s |
| 压缩 | `compressing` | 格式转换压缩（stub） | ~3s |
| 完成 | `completed` | 生成 SPZ/SOG 文件 | - |

> **外部算法一体化**：设置 `ALG_ENABLED=true` 可切换为外部 Docker 镜像模式。按 `scene` 字段路由：commodity 走算法 2，indoor/outdoor 走算法 1。配置项见 `docker-compose.yml` worker 环境变量。

**Stub 模式下总耗时约 15 秒**。

---

## 技术选型

| 层级 | 生产方案 | 本地轻量方案 |
|------|---------|-------------|
| 后端框架 | FastAPI + Pydantic | FastAPI + Pydantic |
| 任务队列 | Celery + Redis | Celery + 内存 broker |
| 数据库 | PostgreSQL + SQLAlchemy | SQLite + SQLAlchemy |
| 对象存储 | MinIO | 本地文件系统 |
| 鉴权 | Authorization Header（app_auth + project_auth） | Authorization Header（app_auth + project_auth） |
| 前端 | 原生 HTML/JS | 原生 HTML/JS |
| 容器化 | Docker Compose | 无需 Docker |
| 测试 | pytest + httpx | pytest + httpx |
