# 3DGS 训练平台 — 系统设计文档

> 语言无关的业务逻辑与架构设计。当前实现为 Python/FastAPI，后续切换到 Java/Vue 时以此为准。

---

## 1. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      客户端（浏览器）                     │
│          上传页面 / 任务列表 / 3D 查看器（SSE）            │
└──────────────┬──────────────────────────────────────────┘
               │ HTTP / SSE
┌──────────────▼──────────────────────────────────────────┐
│                    API 服务（Web 层）                     │
│   POST /tasks (创建)  │  GET /tasks (列表)               │
│   POST /tasks/{id}/start  │  GET /tasks/{id} (查询)      │
│   GET /tasks/{id}/events (SSE)  │  /download (下载)      │
└──────┬───────────────────────────────────────────────────┘
       │ 读写元数据          │ 提交任务
┌──────▼──────────┐   ┌──────▼────────────────────────────┐
│   数据库         │   │        任务队列（消息队列）         │
│  Task / TaskFile │   │   extract → colmap → train → compress│
└──────────┬──────┘   └──────┬────────────────────────────┘
           │                 │
           │          ┌──────▼────────────────────────────┐
           │          │        Worker（任务执行层）         │
           │          │   帧提取 → COLMAP → 训练 → 压缩     │
           │          └──────┬────────────────────────────┘
           │                 │ 输出文件（SPZ/SOG）
           │          ┌──────▼────────────────────────────┐
           │          │        对象存储（OBS/MinIO）        │
           └──────────┤     存储输入/输出文件              │
                      └───────────────────────────────────┘
```

**组件职责：**

| 组件 | 职责 | 对外接口 |
|------|------|---------|
| Web 层 | 接收请求、鉴权、任务生命周期管理、SSE 推送 | REST API |
| 数据库 | 存储任务元数据（状态、进度、文件索引） | SQL |
| TaskRepository | 统一封装 Task/TaskFile 数据库操作，API 注入 + Worker 独立双模式 | Python API |
| 任务队列 | 异步流水线调度，四阶段串联 | 消息 |
| Worker | 执行算法阶段（帧提取/位姿/训练/压缩） | 内部调用 |
| 对象存储 | 存储上传文件和输出文件（MinIO / 本地文件系统双模） | S3 兼容 API |

---

## 2. 核心业务流程

```
用户提交任务
    │
    ▼
创建任务 (POST /tasks)
  入库: Task + TaskFile（元数据）
  返回: uploadInfos（预签名上传 URL）
    │
    ▼
客户端上传文件
  按 uploadInfos 逐项 PUT 文件到 MinIO 或本地上传端点
    │
    ▼
启动任务 (POST /tasks/{id}/start)
  状态: pending → processing
  检查文件存在 → 提交四阶段流水线
    │
    ▼
Worker 执行流水线
  initializing → extracting → colmap → training → compressing
    │                │
    │                ├─ 失败 → status: failed
    │                │
    ▼                │
  status: completed  │
  入库: TaskFile（compressed_model）◄─┘
    │
    ▼
用户轮询/SSE 获取进度
  完成后 → 下载 SPZ/SOG 文件
```

---

## 3. 数据模型

### 3.1 Task（任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string(32) | 主键，Snowflake 递增纯数字，如 `332011480592384` |
| projectId | string(20) | 项目标识 |
| externalCode | string(256) | 外部系统唯一编号（只记录不校验） |
| scene | enum | 场景类型：`commodity` / `indoor` / `outdoor` |
| status | enum | 对外状态：`pending` → `processing` → `completed` / `failed` |
| currentStage | enum | 内部阶段：`initializing` → `extracting` → `colmap` → `training` → `compressing` |
| progress | int | 进度 0–100 |
| remainingTime | int | 预计剩余秒数 |
| createdAt / updatedAt / completedAt | datetime | 时间戳 |
| errorMessage | text | 失败时的错误信息 |

### 3.2 TaskFile（任务文件）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 自增主键 |
| taskId | string(32) | 外键 → Task |
| fileName | string(256) | 原始文件名（含后缀） |
| sha256 | string(64) | 文件 SHA-256 |
| contentLength | int | 文件大小（字节） |
| fileUrl | string(1024) | 存储路径 |
| fileRole | enum | 文件角色：`source_video` / `source_images` / `compressed_model` / `raw_model` |
| mimeType | string(128) | MIME 类型（可选） |

### 3.3 状态机

**对外状态：**
```
pending ──[start]──▶ processing ──[success]──▶ completed
                         │
                         └──[error]───▶ failed
```

**内部阶段（processing 内）：**
```
initializing (0%)
  → extracting (10%-25%, ~2s)
  → colmap (30%-45%, ~3s)
  → training (50%-80%, ~7s)
  → compressing (85%-95%, ~3s)
  → completed (100%)
```

---

## 4. API 约定

### 4.1 鉴权

- 标准 OAuth2 Client Credentials 流程
- 合作方持 `client_id` + `secret`，通过 `POST /auth/token`（Basic Auth）换取 JWT
- 后续请求使用 `Authorization: Bearer <JWT>` Header
- 配置项 `SERVICE_ACCOUNTS` 为空时关闭鉴权（`SERVICE_ACCOUNTS=partner-a:sk-xxx,partner-b:sk-yyy`）
- `JWT_SECRET_KEY` 为 JWT 签名密钥，启用鉴权时必须配置
- `ADMIN_CLIENT_ID` 为空时无管理员豁免；设定后该 clientId 可跨账户查看任务
- SSE / 下载端点额外支持 Query 参数传递 Bearer JWT（浏览器限制）

### 4.2 公共参数

所有接口需要 `projectId` Header（string, max 20）。

### 4.3 响应格式

```json
{
  "ret": { "code": 0, "msg": "success" },
  "taskId": "1780612345678",
  "status": "processing",
  ...
}
```

### 4.4 端点列表

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | /auth/token | Basic Auth | 用 `client_id:secret` 换取 JWT access_token |
| POST | /tasks | Bearer JWT | 创建任务（JSON body），返回预签名上传 URL |
| GET | /tasks | Bearer JWT | 按 projectId 列出任务（按 client_id 隔离） |
| POST | /tasks/{taskId}/start | Bearer JWT | 检查文件 → 启动流水线（校验归属） |
| GET | /tasks/{taskId} | Bearer JWT | 查询状态和输出文件下载 URL（校验归属） |
| GET | /tasks/{taskId}/download/{filename} | Bearer JWT | 下载输出文件（支持 Query 传 JWT） |
| PUT | /tasks/{taskId}/upload/{filename} | Bearer JWT | 本地上传文件（Docker 模式通过 MinIO 预签名 URL 直接上传） |
| GET | /tasks/{taskId}/events | Bearer JWT | SSE 实时进度（支持 Query 传 JWT） |

### 4.5 CreateTaskReq / CreateTaskRsp

请求：
```json
{
  "externalCode": "EXT-001",
  "fileInfos": [{
    "fileName": "scene.mp4",
    "sha256": "abc123...",
    "contentLength": 1048576,
    "fileUrl": "",
    "fileRole": "source_video",
    "mimeType": "video/mp4"
  }],
  "scene": "indoor"
}
```

响应（uploadInfos 为上传 URL 列表）：
```json
{
  "ret": { "code": 0, "msg": "success" },
  "taskId": "332011480592384",
  "uploadInfos": [{
    "objectId": "scene.mp4",
    "fileName": "scene.mp4",
    "url": "/tasks/332011480592384/upload/scene.mp4",
    "method": "PUT",
    "headers": { "Authorization": "...", "Content-Type": "video/mp4" }
  }]
}
```

终端收到后按 uploadInfos 逐项 PUT 文件，再调用 start 启动流水线。

---

## 5. 文件存储模型

| 角色 | 来源 | 存储位置 |
|------|------|---------|
| `source_video` | 用户上传 | MinIO: `tasks/{taskId}/{fileName}`；本地缓存: `{local}/tasks/{taskId}/` |
| `source_images` | 用户上传（N张） | MinIO: `tasks/{taskId}/{fileName}`；本地缓存: `{local}/tasks/{taskId}/` |
| `compressed_model` | compress / finalize 阶段产出 | MinIO: `tasks/{taskId}/output/model.spz`；本地缓存: `{local}/tasks/{taskId}/output/` |
| `raw_model` | finalize 阶段产出 | MinIO: `tasks/{taskId}/output/model.ply`；本地缓存: `{local}/tasks/{taskId}/output/` |

中间产物（frames/colmap/models）仅存本地磁盘，不入库也不上传 MinIO。
上传文件同时写入本地缓存和 MinIO，流水线使用本地缓存；下载时 MinIO 返回预签名 URL（302 重定向），本地模式回退 FileResponse。
本地模式使用 `LocalStorageClient` 替代 MinIO，通过 `USE_LOCAL_STORAGE=true` 切换。

---

## 6. 任务清理策略

| 条件 | 阈值 | 操作 |
|------|------|------|
| status=pending 且 createdAt 超时 | 24h（可配置） | 删除任务 + 文件 |
| status=completed 且 completedAt 超时 | 7d（可配置） | 删除任务 + 文件 |

---

## 7. 技术切换映射

| 当前（Python/FastAPI） | 目标（Java/Vue） |
|------------------------|-----------------|
| FastAPI 路由 | Spring Boot Controller |
| Pydantic Schema | POJO + Validation |
| SQLAlchemy ORM | JPA / MyBatis |
| Celery 任务链 | xxl-job / Quartz 编排 |
| 原生 HTML/JS（无框架） | Vue 3 + Vite SPA |
| SSE (sse-starlette) | Spring WebFlux SSE |
| MinIO Python SDK | MinIO Java SDK |
| SQLite / PostgreSQL | PostgreSQL |

---

## 8. 外部算法一体化模式

通过 `ALG_ENABLED=true` 切换，Worker 通过 `docker run` 调用独立算法镜像：

```
Worker (Celery task)
  └─ subprocess.run(["docker", "run", ...alg_image...])
  └─ 等待退出 → 搜 PLY → 上传 MinIO → 写 DB → completed
```

配置项：

| 配置项 | 说明 |
|--------|------|
| `ALG_ENABLED` | 模式开关 |
| `ALG_IMAGE` | 算法 Docker 镜像 |
| `ALG_SCRIPT` | 入口脚本 |
| `ALG_OUTPUT_DIR` | 输出子目录 |
| `ALG_PLY_NAME` | PLY 文件名 |
| `ALG_PLY_SUBDIR` | PLY 搜索路径 |
| `ALG_HOST_DATA_DIR` | 宿主机数据目录 |
| `ALG_EXPECTED_SECONDS` | 预计执行时间（秒） |
| `ALG_MAX_SECONDS` | 最大超时时间（秒） |

完整接口契约见 `docs/openapi.yaml`，数据库设计见 `docs/database_design.md`。
