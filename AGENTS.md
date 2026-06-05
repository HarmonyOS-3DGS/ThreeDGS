# 3D Gaussian Splatting 工程化平台 —— AI Agent 开发指南

> 本文件面向 AI 编码助手，用于快速理解项目结构、技术栈和开发规范。
> 项目主要使用中文编写注释和文档。

---

## 项目概述

本项目是一个基于 **FastAPI + Celery + SQLAlchemy** 的 3D Gaussian Splatting（3DGS）端到端训练平台，目前处于 **MVP（最小可行产品）阶段**。

**关键前提**：训练相关的核心算法（帧提取、COLMAP、3DGS训练、压缩）均为 **Stub（空壳）实现**，不关注具体算法细节，专注工程架构与前后端衔接。Stub 模式下完整流水线耗时约 **15 秒**。

### 架构

**生产模式（Docker）：**
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

1. **创建任务**（POST /tasks）—— 上传文件 + 注册元数据 → 状态 `queued`
2. **启动任务**（POST /tasks/{id}/start）—— 提交 Celery 链 → 状态 `processing`
3. **轮询/SSE 等待** → 内部阶段：pending → extracting → colmap → training → compressing
4. **完成** → 状态 `completed`，可下载输出文件（SPZ/SOG）

---

## 技术栈

| 层级 | 生产方案 | 本地轻量方案 |
|------|---------|-------------|
| 后端框架 | FastAPI 0.111 + Pydantic 2.7 | 同上 |
| 任务队列 | Celery 5.4 + Redis 5.0 | Celery + 内存 broker（memory://） |
| 数据库 | PostgreSQL 15 + SQLAlchemy 2.0 | SQLite + SQLAlchemy 2.0 |
| 对象存储 | MinIO 7.2 | 本地文件系统（LocalStorageClient） |
| 鉴权 | API Key（X-API-Key Header） | 同上（可留空关闭） |
| 前端 | 原生 HTML / CSS / JS（无框架） | 同上 |
| 容器化 | Docker Compose（六服务编排） | 无需 Docker |
| 测试 | pytest 9.0 + httpx 0.27 + pytest-cov | 同上 |
| Python 版本 | 3.11 | 3.11 |

---

## 项目目录结构

```
.
├── backend/                    # Python 后端
│   ├── api/                    # FastAPI 路由和 Pydantic Schema
│   │   ├── main.py             # FastAPI 入口，挂载静态文件和路由
│   │   ├── deps.py             # 依赖注入（DB session）
│   │   ├── routers/
│   │   │   ├── tasks.py        # POST /tasks, POST /tasks/{id}/start, GET /tasks/{id}
│   │   │   ├── sse.py          # GET /tasks/{id}/events（SSE 实时进度）
│   │   │   ├── upload.py       # [废弃] 旧上传接口，返回 410
│   │   │   └── projects.py     # [废弃] 旧项目查询，返回 410
│   │   └── schemas/
│   │       ├── task.py         # TaskCreate/Start/QueryResponse 等 Pydantic 模型
│   │       └── project.py      # [废弃] 旧版 Project 模型
│   ├── core/                   # 基础设施层
│   │   ├── config.py           # Pydantic Settings 配置（.env 驱动）
│   │   ├── database.py         # SQLAlchemy 引擎、Session、Task + TaskFile ORM 模型
│   │   ├── auth.py             # API Key 鉴权（X-API-Key）
│   │   ├── storage.py          # 存储工厂（MinIO / 本地 自动切换）
│   │   ├── local_storage.py    # 本地文件系统存储实现
│   │   └── minio_storage.py    # MinIO 对象存储实现
│   └── worker/                 # Celery Worker
│       ├── celery_app.py       # Celery 应用配置
│       ├── tasks/              # 四阶段流水线任务
│       │   ├── pipeline.py     # 任务链编排（chain）
│       │   ├── extract_frames.py
│       │   ├── colmap_sfm.py
│       │   ├── train_gs.py
│       │   └── compress.py
│       └── models/             # Stub 模型层
│           ├── preprocessor.py # FFmpeg / COLMAP 空壳
│           ├── trainer.py      # 3DGS 训练空壳
│           └── compressor.py   # PLY→SPZ/SOG 压缩空壳
├── frontend/                   # 静态前端（原生 HTML/JS/CSS）
│   ├── index.html              # 上传页面
│   ├── status.html             # 任务列表页面
│   ├── viewer.html             # 3D 场景查看器（SSE 进度 + iframe）
│   ├── css/style.css
│   └── js/
│       ├── app.js              # 上传表单 + 启动任务
│       └── viewer.js           # SSE 连接 + 查看器集成
├── tests/                      # pytest 测试套件（23 个测试）
│   ├── conftest.py             # 全局 fixture（SQLite 文件模式、TestClient）
│   ├── test_api/               # API 端点测试
│   ├── test_core/              # 核心模块测试（storage mock）
│   └── test_worker/            # Worker 任务测试
├── scripts/                    # 集成测试脚本
│   ├── real_test.py            # 线程内启动 API+Worker 的真实 HTTP 测试
│   └── integration_test.py     # 子进程启动 API+Worker 的集成测试
├── docs/                       # 文档
│   └── openapi.yaml            # OpenAPI 3.0 接口文档
├── docker-compose.yml          # 六服务编排（api / worker / redis / db / minio）
├── Dockerfile.api              # API 服务镜像
├── Dockerfile.worker           # Worker 服务镜像
├── run_local.bat / run_local.sh # 一键本地启动脚本（Windows / Linux）
├── requirements.txt            # Python 依赖
├── pytest.ini                  # pytest 配置（testpaths=tests, 排除 scripts/）
├── .env.example                # 生产环境配置模板
├── .env.local                  # 本地轻量配置（SQLite + 内存 Celery）
└── reference/                  # 参考资料（非代码）
    ├── 3dgs_engineering_guide/ # 3DGS 工程化实践落地指南
    └── 3dgs_roadmap/           # 3DGS 工程化实施路线图
```

---

## 启动与运行

### 方式一：一键本地启动（推荐，无需 Docker）

```bash
# Windows
run_local.bat

# Linux / Mac
bash run_local.sh
```

- 自动使用 `.env.local` 配置（SQLite + 内存 Celery + 本地文件存储）
- 访问地址：
  - 上传页面：`http://localhost:8000/index.html`
  - 查看器：`http://localhost:8000/viewer.html?id={task_id}`
  - API 文档：`http://localhost:8000/docs`

> 本地模式使用 SQLite + 内存 Celery + 本地文件存储，零外部依赖。

### 方式二：Docker Compose（生产模式）

```bash
docker-compose up --build -d
docker-compose ps
```

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
Remove-Item -Force .\3dgs.db -ErrorAction SilentlyContinue
python -c "from backend.core.database import init_db; init_db()"

# 5. 启动 Worker（新开终端）
celery -A backend.worker.celery_app worker --loglevel=info -c 1 --pool=solo

# 6. 启动 API
uvicorn backend.api.main:app --reload --port 8000
```

---

## API 端点与鉴权

所有接口（除静态文件外）需要 `X-API-Key` Header。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks` | 创建任务。Form 参数: `external_code`, `files_meta`(JSON 数组), `files`(UploadFile 列表) |
| POST | `/tasks/{id}/start` | 启动任务。status: queued → processing，提交四阶段 Celery 链 |
| GET | `/tasks/{id}` | 查询任务状态。返回 `{code, status, current_stage, progress, remaining_time, output_files}` |
| GET | `/tasks/{id}/events` | SSE 实时进度推送。每 2s 推送，status/completed/failed 时自动断开 |

旧的 `/upload`、`/projects` 已废弃，返回 410。

### REST 请求示例

```bash
# 1. 创建任务
curl -X POST http://localhost:8000/tasks \
  -H "X-API-Key: 3dgs-dev-2026" \
  -F "external_code=EXT-001" \
  -F 'files_meta=[{"original_filename":"scene.mp4","sha256":"abc123","file_size":1048576}]' \
  -F "files=@scene.mp4"

# 2. 启动任务
curl -X POST http://localhost:8000/tasks/{task_id}/start \
  -H "X-API-Key: 3dgs-dev-2026"

# 3. 查询任务
curl http://localhost:8000/tasks/{task_id} \
  -H "X-API-Key: 3dgs-dev-2026"
```

### 鉴权逻辑

`backend/core/auth.py`：
- `.env` 中 `API_KEY` 留空 → 关闭鉴权（开放访问）
- `API_KEY` 设置值 → 所有请求需带 `X-API-Key: <key>`
- 默认开发 Key：`3dgs-dev-2026`

---

## 数据模型

关键 ORM 模型定义在 `backend/core/database.py`：

### Task 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String(36) UUID | 主键，自动生成 |
| `external_code` | String(255) | 外部系统唯一标识码 |
| `status` | String(50) | 外部状态：queued / processing / completed / failed |
| `current_stage` | String(50) | 内部阶段：pending / extracting / colmap / training / compressing |
| `progress` | Integer | 进度百分比 0-100 |
| `remaining_time` | Integer | 预计剩余秒数（Stub 固定值） |
| `created_at` / `updated_at` / `completed_at` | DateTime | 时间戳 |
| `error_message` | Text | 失败时的错误信息 |

### TaskFile 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 自增主键 |
| `task_id` | String(36) FK | 关联 Task |
| `original_filename` | String(512) | 原始文件名（含后缀） |
| `sha256` | String(64) | 文件 SHA256 哈希 |
| `file_size` | Integer | 文件大小（字节） |
| `file_path` | String(1024) | 文件存储路径 |

---

## 测试

### 运行单元测试

```bash
# 运行全部测试（先删除旧 DB）
Remove-Item -Force .\test.db -ErrorAction SilentlyContinue
pytest -v

# 带覆盖率报告
pytest --cov=backend --cov-report=term-missing
```

测试配置（`tests/conftest.py`）：
- 强制使用 SQLite 文件数据库（`sqlite:///./test.db`）
- Celery 使用内存 broker（`memory://`）
- API Key 固定为 `test-key`
- `TestClient` 自动携带 `X-API-Key` 请求头
- 数据库在 session 结束时自动清理（`Base.metadata.drop_all`）
- `pytest.ini` 中 `testpaths = tests` 且 `norecursedirs` 排除 `scripts/`，防止集成脚本被扫描

### 运行集成测试

```bash
# 线程内集成测试（API + Worker 同进程，真实 HTTP 请求）
python scripts/real_test.py

# 子进程集成测试（独立 API 和 Worker 进程）
python scripts/integration_test.py
```

---

## 配置说明

配置通过 `backend/core/config.py` 中的 `Pydantic Settings` 加载，优先级：环境变量 > `.env` 文件 > 默认值。

关键配置项：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `DATABASE_URL` | `sqlite:///./3dgs.db` | 数据库连接串 |
| `CELERY_BROKER_URL` | `memory://` | Celery Broker |
| `CELERY_RESULT_BACKEND` | `cache+memory://` | Celery 结果后端 |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO 地址 |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO 账号 |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO 密码 |
| `USE_LOCAL_STORAGE` | `false` | 是否强制使用本地文件存储 |
| `LOCAL_STORAGE_DIR` | `./local_storage` | 本地存储根目录 |
| `API_KEY` | `""` | 鉴权 Key（留空关闭） |

---

## 代码风格与开发规范

0. **Git 提交规则**：
   - Author 和 Committer **必须且仅能为** `fryandev <268098688+fryandev@users.noreply.github.com>`。禁止使用任何其他姓名或邮箱，禁止出现真实身份信息。提交前设置：`$env:GIT_COMMITTER_NAME="fryandev"; $env:GIT_COMMITTER_EMAIL="268098688+fryandev@users.noreply.github.com"; git commit --author="fryandev <268098688+fryandev@users.noreply.github.com>"`。
   - **禁止自动提交代码**。只在用户明确要求提交时才提交。提交 message 需基于代码最终 diff 内容概括，而非对话过程。未经用户确认不得执行 commit。
1. **语言**：项目注释、文档、README、前端 UI 文本均使用 **中文**。代码中的字符串常量（如状态值、错误信息）也使用中文。
2. **导入顺序**：标准库 → 第三方库 → 项目内部模块（`backend.*`）
3. **类型注解**：API Schema 使用 Pydantic 2.x 模型；函数参数尽量标注类型
4. **数据库**：使用 SQLAlchemy 2.0 声明式 ORM；所有表通过 `init_db()` 自动创建（无 Alembic 迁移脚本，MVP 阶段简化处理）
5. **任务更新模式**：每个 Celery 任务内部通过 `_update_task()` 辅助函数直接操作数据库，使用 `SessionLocal` 新建独立 session，并用 `try/finally` 确保关闭
6. **异常处理**：Worker 任务中的进度更新（`self.update_state`）使用 `try/except` 静默忽略，避免测试环境无 Celery 上下文时崩溃
7. **存储抽象**：`backend/core/storage.py` 提供懒加载代理，通过 `USE_LOCAL_STORAGE` 环境变量在 MinIO 和本地文件系统之间切换，保持 API 一致

---

## 流水线阶段与状态机

### 外部状态（TaskStatus，对用户暴露）

| 状态值 | 含义 | 说明 |
|--------|------|------|
| `queued` | 排队中 | 任务已创建，等待启动 |
| `processing` | 处理中 | 流水线正在执行 |
| `completed` | 完成 | 全部阶段执行成功 |
| `failed` | 失败 | 流水线执行出错 |

### 内部阶段（TaskStage，通过 current_stage 暴露）

| 阶段值 | 含义 | 进度范围 | Stub 耗时 |
|--------|------|---------|----------|
| `pending` | 等待中 | 0% | - |
| `extracting` | 帧提取中 | 10% - 25% | ~2s |
| `colmap` | COLMAP SfM 中 | 30% - 45% | ~3s |
| `training` | 3DGS 训练中 | 50% - 80% | ~7s |
| `compressing` | 压缩中 | 85% - 95% | ~3s |
| `completed` | 完成 | 100% | - |
| `failed` | 失败 | - | - |

Celery 任务链在 `backend/worker/tasks/pipeline.py` 中通过 `celery.chain` 编排：
```python
chain(
    extract_frames.s(task_id, video_path, fps=5),
    run_colmap.s(),
    train_gaussian_splatting.s(iterations=30000),
    compress_result.s(),
)
```
各阶段通过 `prev_result: dict` 累加传递路径参数：`task_id → frames_dir → colmap_dir → model_path → compressed_spz/sog`

---

## 前端架构

- **无构建工具**：纯 HTML/CSS/JS，直接由 FastAPI `StaticFiles` 挂载服务
- **API Key 硬编码**：`frontend/js/app.js` 和 `frontend/js/viewer.js` 中硬编码默认 Key `3dgs-dev-2026`，与 `.env` 默认值保持一致
- **实时进度**：使用 SSE（`EventSource`）连接 `/tasks/{id}/events`，每 2 秒推送一次状态
- **上传流程**：`index.html` 表单 → `app.js` 计算文件 SHA256 → POST `/tasks` 创建任务 → 点击"启动任务" → POST `/tasks/{id}/start`
- **查看器**：`viewer.html` 通过 URL 参数 `?id=` 获取 task_id，SSE 连接实时更新进度条

---

## 安全注意事项

1. **API Key**：生产环境必须设置强随机 `API_KEY`，前端硬编码的 Key 仅用于开发测试
2. **CORS**：`backend/api/main.py` 中配置 `allow_origins=["*"]`，生产环境应限制为具体域名
3. **文件上传**：`tasks.py` 将上传文件保存到 `local_storage/uploads/{task_id}/`，未做文件类型深度校验，生产需加强
4. **MinIO**：默认使用 `minioadmin/minioadmin`，生产必须修改
5. **.env 文件**：`.env` 和 `.env.local` 已加入 `.gitignore`，禁止提交密钥

---

## 扩展与迭代方向

当前代码为 MVP 架构，以下模块设计为可替换的 Stub，后续迭代时直接替换实现即可：

| Stub 文件 | 当前行为 | 未来替换目标 |
|-----------|---------|-------------|
| `backend/worker/models/preprocessor.py` | 生成 dummy 帧和 COLMAP 文本文件 | 真实 FFmpeg 帧提取 + COLMAP CLI 调用 |
| `backend/worker/models/trainer.py` | 生成最小 PLY 文件 | gsplat / Nerfstudio 训练循环 |
| `backend/worker/models/compressor.py` | 生成 dummy SPZ/SOG 文件 | 3dgsconverter / 自定义压缩工具 |

Worker 任务的接口签名（输入/输出字典结构）应保持不变，以确保 Celery 任务链无需修改。

---

## 常见开发命令速查

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -c "from backend.core.database import init_db; init_db()"

# 运行 API 服务
uvicorn backend.api.main:app --reload --port 8000

# 运行 Worker
celery -A backend.worker.celery_app worker --loglevel=info -c 1 --pool=solo

# 运行测试
pytest -v
pytest --cov=backend --cov-report=term-missing

# 集成测试
python scripts/real_test.py
python scripts/integration_test.py

# Docker 启动
docker-compose up --build -d
```
