# 3D Gaussian Splatting 工程化平台 —— AI Agent 开发指南

> 本文件面向 AI 编码助手，用于快速理解项目结构、技术栈和开发规范。
> 项目主要使用中文编写注释和文档。

---

## 项目概述

本项目是一个基于 **FastAPI + Celery + SQLAlchemy** 的 3D Gaussian Splatting（3DGS）端到端训练平台，目前处于 **MVP（最小可行产品）阶段**。

**关键前提**：训练相关的核心算法（帧提取、COLMAP、3DGS训练、压缩）均为 **Stub（空壳）实现**，不关注具体算法细节，专注工程架构与前后端衔接。Stub 模式下完整流水线耗时约 **15 秒**。

### 架构

**生产模式（Docker Compose）：**
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

**本地轻量模式（无 Docker）：**
```
用户浏览器 → FastAPI (创建任务 / 启动 / 查询 / SSE)
                ↓
        SQLite (本地文件)      内存 Celery (无需 Redis)
                ↓                        ↓
        Celery Worker (四阶段链)
                ↓
        本地文件系统 (替代 MinIO)
```

### 核心流程

1. **创建任务**（`POST /tasks`）—— 提交 JSON body → 注册元数据 → 返回预签名上传 URL → 状态 `pending`
2. **客户端上传文件** —— 按 `uploadInfos` 逐项 PUT 文件到 MinIO / 本地上传端点
3. **启动任务**（`POST /tasks/{id}/start`）—— 检查文件存在 → 提交 Celery 链 → 状态 `processing`
4. **轮询 / SSE 等待** → 内部阶段：`initializing` → `extracting` → `colmap` → `training` → `compressing`
5. **完成** → 状态 `completed`，可下载输出文件（SPZ / SOG）

---

## 技术栈

| 层级 | 生产方案 | 本地轻量方案 |
|------|---------|-------------|
| 后端框架 | FastAPI 0.111 + Pydantic 2.7 | 同上 |
| 任务队列 | Celery 5.4 + Redis 7 | Celery + 内存 broker（`memory://`） |
| 数据库 | PostgreSQL 15 + SQLAlchemy 2.0 | SQLite + SQLAlchemy 2.0 |
| 对象存储 | MinIO 7.2 | 本地文件系统（`LocalStorageClient`） |
| 鉴权 | `Authorization` Header（`app_auth` + `project_auth`） | 同上（`API_KEY` 留空关闭鉴权） |
| 前端 | 原生 HTML / CSS / JS（无构建工具） | 同上 |
| 容器化 | Docker Compose（5 服务编排） | 无需 Docker |
| 测试 | pytest 8.2 + httpx 0.27 + pytest-cov 5.0 + pytest-asyncio 0.23.8 | 同上 |
| Python 版本 | 3.11 | 3.11 |

### 关键依赖版本（`requirements.txt`）

- `fastapi==0.111.0`
- `uvicorn[standard]==0.30.0`
- `pydantic==2.7.0` / `pydantic-settings==2.2.0`
- `sqlalchemy==2.0.30`
- `alembic==1.13.0`
- `psycopg2-binary==2.9.9`
- `celery==5.4.0`
- `redis==5.0.0`
- `minio==7.2.0`
- `httpx==0.27.0`
- `pytest==8.2.0` / `pytest-asyncio==0.23.8` / `pytest-cov==5.0.0`
- `python-multipart==0.0.9`
- `aiofiles==23.2.0`
- `sse-starlette==2.1.0`
- `uuid-utils==0.6.0`

---

## 项目目录结构

```
.
├── backend/                    # Python 后端
│   ├── api/                    # FastAPI 路由和 Pydantic Schema
│   │   ├── main.py             # FastAPI 入口，挂载静态文件和路由，启动时初始化数据库
│   │   ├── deps.py             # 依赖注入（DB session 封装）
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── tasks.py        # POST /tasks, GET /tasks, POST /tasks/{id}/start, GET /tasks/{id}, GET /tasks/{id}/download
│   │   │   └── sse.py          # GET /tasks/{id}/events（SSE 实时进度）
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── task.py         # CreateTaskReq / CreateTaskRsp / StartTaskRsp / GetTaskRsp / TaskListResponse / TaskStatusEvent / FileInfo / UrlInfo
│   ├── core/                   # 基础设施层
│   │   ├── __init__.py
│   │   ├── config.py           # Pydantic Settings 配置（`.env` 驱动，含默认值）
│   │   ├── database.py         # SQLAlchemy 引擎、Session、Base、init_db()
│   │   ├── repository.py      # TaskRepository 数据访问层（API 注入 / Worker 独立双模式）
│   │   ├── file_utils.py      # 文件魔数校验（detect_mime）
│   │   ├── id_generator.py    # Snowflake ID 生成器（纯数字递增）
│   │   ├── auth.py             # Authorization 鉴权（app_auth + project_auth，API_KEY 留空则关闭鉴权）
│   │   ├── task_publisher.py  # API-Worker 解耦桥接（懒加载 + 注册回调）
│   │   ├── interfaces.py      # StorageClient Protocol 抽象接口
│   │   ├── storage.py          # 存储工厂（USE_LOCAL_STORAGE 控制 MinIO / 本地切换）
│   │   ├── local_storage.py    # 本地文件系统存储实现（LocalStorageClient）
│   │   ├── minio_storage.py    # MinIO 对象存储封装（MinioStorageClient）
│   │   └── models/             # ORM 模型（从 database.py 拆分）
│   │       ├── __init__.py
│   │       ├── task.py         # Task 模型 + TaskStatus / TaskStage 枚举
│   │       └── task_file.py    # TaskFile 模型
│   └── worker/                 # Celery Worker
│       ├── __init__.py
│       ├── celery_app.py       # Celery 应用配置 + Beat 定时任务调度
│       ├── models/             # Stub 模型层
│       │   ├── __init__.py
│       │   ├── preprocessor.py # FFmpeg / COLMAP 空壳（生成 dummy 帧和文本文件）
│       │   ├── trainer.py      # 3DGS 训练空壳（生成最小 PLY 文件）
│       │   └── compressor.py   # PLY→SPZ/SOG 压缩空壳（生成 dummy 二进制文件）
│       └── tasks/              # 四阶段流水线 + 定时清理
│           ├── __init__.py
│           ├── pipeline.py     # 任务链编排（celery.chain）
│           ├── shared.py       # 公共函数（task_output_path）
│           ├── extract_frames.py
│           ├── colmap_sfm.py
│           ├── train_gs.py
│           ├── compress.py
│           └── cleanup.py      # 过期 pending / completed 任务清理（Celery Beat）
├── frontend/                   # 静态前端（原生 HTML/JS/CSS，无构建工具）
│   ├── index.html              # 上传页面（创建任务 + 启动训练）
│   ├── status.html             # 任务列表页面（轮询刷新）
│   ├── viewer.html             # 3D 场景查看器（SSE 进度 + 下载链接）
│   ├── css/style.css
│   └── js/
│       ├── app.js              # 上传表单 + 启动任务 + 任务列表轮询
│       └── viewer.js           # SSE 连接 + 状态展示 + 下载链接加载
├── tests/                      # pytest 测试套件
│   ├── conftest.py             # 全局 fixture（SQLite 文件模式 test.db、TestClient、DB 自动清理）
│   ├── test_api/               # API 端点测试
│   │   ├── __init__.py
│   │   ├── test_upload.py      # 创建任务（JSON / multipart / 参数校验）
│   │   ├── test_projects.py    # 查询任务、启动任务、状态流转
│   │   └── test_sse.py         # SSE 端点连通性
│   ├── test_core/              # 核心模块测试
│   │   ├── __init__.py
│   │   └── test_storage.py     # MinIO 客户端 mock 测试
│   └── test_worker/            # Worker 任务测试
│       ├── __init__.py
│       ├── test_extract_frames.py
│       ├── test_colmap.py
│       ├── test_train.py
│       ├── test_compress.py
│       ├── test_pipeline.py    # 任务链编排 mock 测试
│       └── test_cleanup.py     # 过期任务清理逻辑测试
├── scripts/                    # 集成测试脚本
│   ├── real_test.py            # 线程内启动 API + Worker 的真实 HTTP 测试（推荐）
│   └── integration_test.py     # 子进程启动 API + Worker 的集成测试（字段名较旧，可能需更新）
├── docs/                       # 文档
│   ├── openapi.yaml            # OpenAPI 3.0 接口文档
│   └── reference_guide.md      # 参考指南
├── docker-compose.yml          # 5 服务编排（api / worker / redis / db / minio）+ 3 个卷
├── Dockerfile.api              # API 服务镜像（python:3.11-slim）
├── Dockerfile.worker           # Worker 服务镜像（python:3.11-slim）
├── run_local.bat               # Windows 一键本地启动脚本
├── run_local.sh                # Linux / Mac 一键本地启动脚本
├── requirements.txt            # Python 依赖（精确版本锁定）
├── pytest.ini                  # pytest 配置（testpaths=tests, asyncio_mode=auto, 排除 scripts/）
├── .env.example                # 生产环境配置模板（PostgreSQL + Redis + MinIO）
├── .env.local                  # 本地轻量配置（SQLite + 内存 Celery + 本地存储）
├── .gitignore                  # 忽略 .env / *.db / local_storage / .venv / .kimi / 等
└── reference/                  # 参考资料（非代码）
    ├── 3dgs_engineering_guide/
    ├── 3dgs_roadmap/
    └── Kimi_Agent_3D高斯API演示/
```

---

## 配置说明

配置通过 `backend/core/config.py` 中的 `Pydantic Settings` 加载，优先级：**环境变量 > `.env` 文件 > 默认值**。`env_file = ".env"`，编码 `utf-8`。

关键配置项：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `DATABASE_URL` | `sqlite:///./3dgs.db` | 数据库连接串 |
| `CELERY_BROKER_URL` | `memory://` | Celery Broker |
| `CELERY_RESULT_BACKEND` | `cache+memory://` | Celery 结果后端 |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO 地址 |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO 账号 |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO 密码 |
| `MINIO_BUCKET` | `gaussian` | MinIO 存储桶 |
| `MINIO_SECURE` | `false` | MinIO 是否使用 HTTPS |
| `MINIO_PUBLIC_ENDPOINT` | `""` | MinIO 外部访问地址（预签名 URL 用，留空则用 `MINIO_ENDPOINT`） |
| `USE_LOCAL_STORAGE` | `false` | 是否强制使用本地文件存储 |
| `LOCAL_STORAGE_DIR` | `./local_storage` | 本地存储根目录 |
| `API_KEY` | `""` | 鉴权 Key（留空关闭鉴权） |
| `API_HOST` | `0.0.0.0` | API 监听地址 |
| `API_PORT` | `8000` | API 监听端口 |
| `TASK_PENDING_TTL_HOURS` | `24` | 过期 pending 任务清理阈值（小时） |
| `TASK_COMPLETED_TTL_DAYS` | `7` | 过期 completed 任务清理阈值（天） |
| `DEFAULT_FPS` | `5` | 帧提取默认帧率 |
| `DEFAULT_ITERATIONS` | `30000` | 3DGS 训练默认迭代次数 |

---

## 启动与运行

### 方式一：一键本地启动（推荐，无需 Docker）

```bash
# Windows
run_local.bat

# Linux / Mac
bash run_local.sh
```

脚本行为：
1. 自动复制 `.env.local` → `.env`
2. 创建 `local_storage/` 和 `uploads/` 目录
3. 初始化数据库（调用 `init_db()`）
4. 在同 Python 进程内以线程方式启动 Celery Worker + FastAPI，使 `memory://` broker 可被共享

访问地址：
- 上传页面：`http://localhost:8000/index.html`
- 任务列表：`http://localhost:8000/status.html`
- 查看器：`http://localhost:8000/viewer.html?id={task_id}&projectId={project_id}`
- API 文档：`http://localhost:8000/docs`

### 方式二：Docker Compose（生产模式）

```bash
docker-compose up --build -d
docker-compose ps
```

编排服务：`api`、`worker`、`redis`、`db`（postgres:15-alpine）、`minio`。

### 方式三：手动分步启动

```bash
# 1. 创建虚拟环境
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

# 2. 安装依赖（Windows 需代理）
# $env:HTTP_PROXY="http://proxyhes-gy.security.huawei.com:8080"
# pip install --proxy $env:HTTP_PROXY -r requirements.txt
pip install -r requirements.txt

# 3. 选择配置
cp .env.local .env          # 本地轻量模式
cp .env.example .env       # 生产模式（需 PostgreSQL + Redis + MinIO）

# 4. 初始化数据库（先删除旧 DB 避免 schema 冲突）
(Windows)Remove-Item -Force .\3dgs.db -ErrorAction SilentlyContinue
(linux)rm -f 3dgs.db
python -c "from backend.core.database import init_db; init_db()"

# 5. 启动（二选一）
# 方式 A：同进程线程模式（memory broker 共享，无需 Redis）
python run_local.py

# 方式 B：分进程启动（需 Redis 等进程间共享 broker）
#   cp .env.local .env
#   # 修改 .env 中 CELERY_BROKER_URL=redis://localhost:6379/0
#   redis-server &
#   celery -A backend.worker.celery_app worker --loglevel=info -c 1 --pool=solo
#   uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## API 端点与鉴权

### 鉴权策略

所有接口（除静态文件外）需要 `Authorization` Header，分为两种策略：

| 策略 | 适用接口 | 说明 |
|------|---------|------|
| `app_auth` | `POST /tasks` | 应用级鉴权，创建任务 |
| `project_auth` | `GET /tasks`, `POST /tasks/{id}/start`, `GET /tasks/{id}`, `GET /tasks/{id}/events`, `GET /tasks/{id}/download` | 项目级鉴权 |

所有接口还需 `projectId` Header（最大 20 字符）。

鉴权逻辑（`backend/core/auth.py`）：
- `.env` 中 `API_KEY` 留空 → **关闭鉴权**（开放访问）
- `API_KEY` 设置值 → 所有请求需带 `Authorization: <key>`
- 默认开发 Key：`3dgs-dev-2026`

SSE 端点额外支持 Query 参数传递鉴权信息（`projectId` 和 `Authorization`），因为浏览器 `EventSource` 不支持自定义 Header。

### 端点列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks` | 创建任务。Body: JSON（`externalCode` + `fileInfos` 数组 + `scene` 枚举 `commodity/indoor/outdoor`），返回 `uploadInfos` 上传 URL |
| GET | `/tasks` | 列出指定项目的所有任务（按 `created_at` 降序） |
| POST | `/tasks/{id}/start` | 启动任务。检查文件已上传，`pending` → `processing`，提交 Celery 链 |
| GET | `/tasks/{id}` | 查询任务状态、进度、输出文件下载 URL |
| GET | `/tasks/{id}/download/{filename}` | 下载任务输出文件 |
| PUT | `/tasks/{id}/upload/{filename}` | 本地上传文件（Docker 模式通过 MinIO 预签名 URL 直接 PUT） |
| GET | `/tasks/{id}/events` | SSE 实时进度推送（每 2 秒一条 `status` 事件，完成或失败时发送 `done` 事件） |

### REST 请求示例

```bash
# 1. 创建任务（JSON）
curl -X POST http://localhost:8000/tasks \
  -H "Authorization: 3dgs-dev-2026" \
  -H "projectId: proj-01" \
  -H "Content-Type: application/json" \
  -d '{"externalCode":"EXT-001","fileInfos":[{"fileName":"test.mp4","sha256":"abc","contentLength":16,"fileUrl":""}],"scene":"indoor"}'

# 2. 启动任务
curl -X POST http://localhost:8000/tasks/{task_id}/start \
  -H "Authorization: 3dgs-dev-2026" \
  -H "projectId: proj-01"

# 3. 查询任务
curl http://localhost:8000/tasks/{task_id} \
  -H "Authorization: 3dgs-dev-2026" \
  -H "projectId: proj-01"

# 4. 下载文件
curl "http://localhost:8000/tasks/{task_id}/download?file=model.spz" \
  -H "Authorization: 3dgs-dev-2026" \
  -H "projectId: proj-01"
```

---

## 数据模型

关键 ORM 模型定义在 `backend/core/models/`，使用 SQLAlchemy 2.0 声明式基类，**无 Alembic 迁移脚本**，MVP 阶段通过 `init_db()` 自动建表。

> 📖 详细数据库设计文档见 `docs/database_design.md`，包含完整字段表、索引、状态流转图。修改 ORM 模型后请同步更新该文档。

### Task 模型（`tasks` 表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `String(32)` PK | 主键，Snowflake 递增纯数字，如 `332011480592384` |
| `project_id` | `String(20)` | 项目 ID（Header 传入），带索引 |
| `external_code` | `String(256)` | 外部系统唯一标识码，带索引 |
| `scene` | `String(32)` | 场景类型：`commodity` / `indoor` / `outdoor` |
| `status` | `String(50)` | 外部状态：`pending` / `processing` / `completed` / `failed` |
| `current_stage` | `String(50)` | 内部阶段：`initializing` / `extracting` / `colmap` / `training` / `compressing` / `completed` / `failed` |
| `progress` | `Integer` | 进度百分比 0–100 |
| `remaining_time` | `Integer` | 预计剩余秒数（Stub 固定 15 秒，按 `max(0, 15 - progress // 7)` 递减） |
| `created_at` | `DateTime` | 创建时间（UTC） |
| `updated_at` | `DateTime` | 更新时间（UTC，`onupdate=datetime.utcnow`） |
| `completed_at` | `DateTime` | 完成时间（可为空） |
| `error_message` | `Text` | 失败时的错误信息 |

关系：`Task.files` ↔ `TaskFile.task`（`cascade="all, delete-orphan"`）

### TaskFile 模型（`task_files` 表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `Integer` PK AI | 自增主键 |
| `task_id` | `String(32)` FK | 关联 `tasks.id` |
| `fileName` | `String(256)` | 原始文件名（ORM 中使用驼峰命名） |
| `sha256` | `String(64)` | 文件 SHA256 哈希 |
| `contentLength` | `Integer` | 文件大小（字节） |
| `fileUrl` | `String(1024)` | 文件存储路径（本地绝对路径或 MinIO 对象名） |
| `fileRole` | `String(50)` | 文件角色：`source_video` / `source_images` / `compressed_model` |
| `mimeType` | `String(128)` | MIME 类型（可选） |

---

## 代码组织与模块划分

### 后端分层

1. **`backend/api/`** —— Web 层
   - `main.py`：FastAPI 应用实例、CORS 中间件、静态文件挂载、数据库启动初始化
   - `routers/tasks.py`：任务生命周期管理（创建、列表、启动、查询、下载）
   - `routers/sse.py`：SSE 长连接实时推送任务状态
   - `schemas/task.py`：Pydantic 请求/响应模型
   - `deps.py`：`get_database` 依赖注入封装

2. **`backend/core/`** —— 基础设施层
   - `config.py`：全局配置单例 `settings`
   - `database.py`：SQLAlchemy 引擎、`SessionLocal`、`Base`、`get_db()` generator。ORM 模型定义已迁移至 `models/` 子模块
   - `models/task.py`：`Task` ORM、`TaskStatus`/`TaskStage` 枚举、`_generate_task_id()`
   - `models/task_file.py`：`TaskFile` ORM
   - `repository.py`：`TaskRepository` 数据访问层，统一封装 DB 操作。支持 API 注入 Session 和 Worker 独立 Session 双模式
   - `file_utils.py`：`detect_mime()` 通过文件头魔数校验真实 MIME 类型，防止后缀伪造
   - `id_generator.py`：Snowflake 简化版 ID 生成器，15 位纯数字递增
   - `auth.py`：`_verify_auth_key` 公共逻辑 + `verify_app_auth` / `verify_project_auth`
   - `storage.py`：懒加载代理 `_LazyStorage`，工厂函数 `get_storage()`
   - `local_storage.py` / `minio_storage.py`：统一接口（`upload_file` / `download_file` / `get_presigned_url` / `delete_object` / `put_object`）

3. **`backend/worker/`** —— 任务执行层
   - `celery_app.py`：Celery 实例、`beat_schedule`（每 30 分钟清理 pending，每小时清理 completed）
   - `tasks/*.py`：Celery 任务定义 + 流水线编排
   - `models/*.py`：Stub 实现，后续替换为真实算法

### 前端架构

- **无构建工具**：纯 HTML/CSS/JS，直接由 FastAPI `StaticFiles(directory="frontend", html=True)` 挂载
- **API Key 硬编码**：`frontend/js/app.js` 和 `frontend/js/viewer.js` 中硬编码默认 Key `3dgs-dev-2026`
- **上传页面**（`index.html`）：表单包含 `projectId`、`externalCode`、`scene`、`files`，`app.js` 计算 SHA-256 后构造 `multipart/form-data` 提交
- **任务列表**（`status.html`）：`app.js` 每 5 秒轮询 `GET /tasks`，展示阶段、进度、剩余时间、查看链接
- **查看器**（`viewer.html`）：`viewer.js` 通过 URL 参数获取 `id` 和 `projectId`，建立 SSE 连接实时更新进度条；完成后展示下载链接

---

## 流水线阶段与状态机

### 外部状态（`TaskStatus`，对用户暴露）

| 状态值 | 含义 | 说明 |
|--------|------|------|
| `pending` | 排队中 | 任务已创建，等待启动 |
| `processing` | 处理中 | 流水线正在执行 |
| `completed` | 完成 | 全部阶段执行成功 |
| `failed` | 失败 | 流水线执行出错 |

### 内部阶段（`TaskStage`，通过 `current_stage` 暴露）

| 阶段值 | 含义 | 进度范围 | Stub 耗时 |
|--------|------|---------|----------|
| `initializing` | 等待中 | 0% | - |
| `extracting` | 帧提取中 | 10% → 25% | ~2s |
| `colmap` | COLMAP SfM 中 | 30% → 45% | ~3s |
| `training` | 3DGS 训练中 | 50% → 80% | ~7s |
| `compressing` | 压缩中 | 85% → 95% | ~3s |
| `completed` | 完成 | 100% | - |
| `failed` | 失败 | - | - |

Celery 任务链在 `backend/worker/tasks/pipeline.py` 中通过 `celery.chain` 编排：

```python
chain(
    extract_frames.s(task_id, video_path, fps=settings.default_fps),
    run_colmap.s(),
    train_gaussian_splatting.s(iterations=settings.default_iterations),
    compress_result.s(),
)
```

各阶段通过 `prev_result: dict` 累加传递路径参数：`task_id` → `frames_dir` → `colmap_dir` → `model_path` → `compressed_spz` / `compressed_sog`。

每个 Worker 任务内部通过 `backend/worker/tasks/shared.py` 中的 `update_task()` 直接操作数据库，使用 `SessionLocal` 新建独立 session，并用 `try/finally` 确保关闭。进度更新中的 `self.update_state` 使用 `try/except` 静默忽略，避免测试环境无 Celery 上下文时崩溃。

---

## 测试策略

### 测试框架与配置

- `pytest.ini`：
  - `testpaths = tests`
  - `norecursedirs = scripts reference .git .venv`
  - `asyncio_mode = auto`
- `tests/conftest.py`：
  - 强制环境变量：`DATABASE_URL=sqlite:///./test.db`、`CELERY_BROKER_URL=memory://`、`API_KEY=test-key`
  - `TestClient` 自动携带 `Authorization: test-key`
  - 使用 `TestingSessionLocal` 覆盖 `get_db` 依赖
  - `setup_db` fixture（`session` 级别、`autouse`）：`Base.metadata.create_all` → `init_db()` → yield → `Base.metadata.drop_all`

### 单元测试结构

| 文件 | 测试内容 |
|------|---------|
| `test_api/test_upload.py` | JSON / multipart 创建任务、必填参数缺失、缺少 `projectId` |
| `test_api/test_projects.py` | 查询任务、启动任务、重复启动、启动后状态变更 |
| `test_api/test_sse.py` | SSE 端点连通性、`text/event-stream` Content-Type、不存在任务 |
| `test_core/test_storage.py` | MinIO 客户端的 `upload_file` / `download_file` / `get_presigned_url` / `delete_object` mock 测试 |
| `test_worker/test_extract_frames.py` | 帧提取任务执行 |
| `test_worker/test_colmap.py` | COLMAP 任务执行 |
| `test_worker/test_train.py` | 训练任务执行 |
| `test_worker/test_compress.py` | 压缩任务执行 |
| `test_worker/test_pipeline.py` | `submit_training_pipeline` 的 `chain` mock 断言 |
| `test_worker/test_cleanup.py` | 过期 pending / completed 任务清理逻辑（边界条件：刚好过期、未过期、非目标状态） |

### 运行测试

```bash
# 运行全部测试（先删除旧 DB）
rm -f test.db
pytest -v

# 带覆盖率报告
pytest --cov=backend --cov-report=term-missing
```

### 集成测试

```bash
# 线程内集成测试（API + Worker 同进程，真实 HTTP 请求，~20 秒）
python scripts/real_test.py

# 子进程集成测试（独立 API 和 Worker 进程）
python scripts/integration_test.py
```

> 注意：`scripts/integration_test.py` 中部分字段名和 Header 方式较旧，与当前 API 实现不完全一致，优先使用 `scripts/real_test.py`。

---

## 代码风格与开发规范

0. **Git 提交规则**：
   - Author 和 Committer **必须且仅能为** `fryandev <268098688+fryandev@users.noreply.github.com>`。禁止使用任何其他姓名或邮箱，禁止出现真实身份信息。
    - **禁止自动提交代码**。只在用户明确要求提交时才提交。提交 message 需基于代码最终 diff 内容概括，而非对话过程。未经用户确认不得执行 commit。
0.1 **测试覆盖**：
    - 每次代码修改后必须运行 `pytest` 验证，确保已有测试通过
    - 新增功能/分支/异常路径必须添加对应测试用例
    - 修改接口/模型后检查相关测试代码是否需要同步修改
    - 目标覆盖率不低于 80%
0.2 **代码格式化**：
    - 每次修改完成后必须执行 `ruff format .` 格式化代码
    - 必须执行 `ruff check .` 检查代码规范，确保零错误
    - 检查通过后方可提交
0.3 **提交前确认**：
    - 最终提交前必须询问用户是否已启动服务测试通过
    - 用户确认服务测试正常后才能执行 commit 和 push
    - 涉及 Docker 部署的改动，需确认 `docker compose up --build -d` 和 `docker_test.sh` 均通过

1. **语言**：项目注释、文档、README、前端 UI 文本均使用 **中文**。代码中的字符串常量（如状态值、错误信息）也使用中文。

2. **导入顺序**：标准库 → 第三方库 → 项目内部模块（`backend.*`）

3. **类型注解**：API Schema 使用 Pydantic 2.x 模型；函数参数尽量标注类型

4. **数据库**：
   - 使用 SQLAlchemy 2.0 声明式 ORM
   - 所有表通过 `init_db()` 自动创建（无 Alembic 迁移脚本，MVP 阶段简化处理）
   - SQLite 场景需设置 `connect_args={"check_same_thread": False}`

5. **任务更新模式**：每个 Celery 任务内部通过 `backend/core/repository.py` 中的 `TaskRepository.update_progress()` 静态方法直接操作数据库，使用 `SessionLocal` 新建独立 session，并用 `try/finally` 确保关闭。`shared.py` 中的旧 `update_task()` 包装已移除。

6. **异常处理**：Worker 任务中的进度更新（`self.update_state`）使用 `try/except` 静默忽略，避免测试环境无 Celery 上下文时崩溃

7. **存储抽象**：`backend/core/storage.py` 提供懒加载代理，通过 `USE_LOCAL_STORAGE` 环境变量在 MinIO 和本地文件系统之间切换，保持 API 一致

8. **文件路径安全**：上传处理中使用 `os.path.basename()` 防止路径遍历（`tasks.py` 中的 `_safe_filename`）

9. **返回值封装**：API 统一返回 `{"ret": {"code": 0, "msg": "success"}, ...}` 结构（由 Pydantic 模型 `ConnectRet` 提供默认值）

---

## 安全注意事项

1. **API Key**：生产环境必须设置强随机 `API_KEY`，前端硬编码的 Key `3dgs-dev-2026` 仅用于开发测试
2. **CORS**：`backend/api/main.py` 中配置 `allow_origins=["*"]`，`allow_credentials=False`，生产环境应限制为具体域名
3. **文件上传**：`tasks.py` 将上传文件保存到 `local_storage/tasks/{task_id}/`，仅做 `os.path.basename()` 防穿越；后端通过 `detect_mime()` 校验文件头魔数（视频/图片角色不符则拒绝）
4. **MinIO**：默认使用 `minioadmin/minioadmin`，生产必须修改
5. **.env 文件**：`.env` 和 `.env.local` 已加入 `.gitignore`，禁止提交密钥
6. **数据库连接**：`pool_pre_ping=True` 用于生产环境连接保活；SQLite 默认 `check_same_thread=False`

---

## 扩展与迭代方向

当前代码为 MVP 架构，以下模块设计为可替换的 Stub，后续迭代时直接替换实现即可：

| Stub 文件 | 当前行为 | 未来替换目标 |
|-----------|---------|-------------|
| `backend/worker/models/preprocessor.py` | 生成 dummy 帧和 COLMAP 文本文件 | 真实 FFmpeg 帧提取 + COLMAP CLI 调用 |
| `backend/worker/models/trainer.py` | 生成最小 PLY 文件 | gsplat / Nerfstudio 训练循环 |
| `backend/worker/models/compressor.py` | 生成 dummy SPZ/SOG 文件 | 3dgsconverter / 自定义压缩工具 |

Worker 任务的接口签名（输入/输出 `dict` 结构）应保持不变，以确保 Celery 任务链无需修改。

---

## 常见开发命令速查

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -c "from backend.core.database import init_db; init_db()"

# 运行 API 服务
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000

# 运行 Worker
celery -A backend.worker.celery_app worker --loglevel=info -c 1 --pool=solo

# 运行测试
rm -f test.db
pytest -v
pytest --cov=backend --cov-report=term-missing

# 代码格式化
ruff format .
ruff check .
ruff check --fix .

# 集成测试
python scripts/real_test.py
python scripts/integration_test.py

# Docker 构建 + 端到端测试
docker compose up --build -d
bash scripts/docker_test.sh

# Docker 启动
docker-compose up --build -d
```
