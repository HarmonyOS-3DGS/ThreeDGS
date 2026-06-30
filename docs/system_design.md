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
│  Task / TaskFile │   │   extract → colmap → train → finalize│
└──────────┬──────┘   └──────┬────────────────────────────┘
           │                 │
           │          ┌──────▼────────────────────────────┐
           │          │        Worker（任务执行层）         │
            │          │   帧提取 → COLMAP → 训练 → 终化     │
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
  检查文件存在 → 提交流水线（Stub 四阶段链或外部算法 Docker）
    │
    ▼
  Worker 执行流水线（Stub 模式）
  initializing → extracting → colmap → training → compressing
      │                │
      │                ├─ 失败 → status: failed
      │                │
      ▼                │
  外部算法模式：commodity_algorithm / external_algorithm（跳过低阶内部阶段）
      │                │
      ▼                │
  status: completed   │
  入库: TaskFile（raw_model / compressed_model）◄─┘
    │
    ▼
用户轮询/SSE 获取进度
  完成后 → 下载 PLY / SPZ / SOG 文件
```

---

## 3. 数据模型

### 3.1 Task（任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string(32) | 主键，Snowflake 递增纯数字，如 `332011480592384` |
| projectId | string(20) | 项目标识 |
| externalCode | string(256) | 外部系统唯一编号（只记录不校验） |
| clientId | string(64) | 任务所属 client，JWT 中提取，用于数据隔离 |
| scene | enum | 场景类型：`commodity` / `indoor` / `outdoor` |
| status | enum | 对外状态：`pending` → `processing` → `completed` / `failed` |
| currentStage | enum | 内部阶段：`initializing` → `extracting` → `colmap` → `training` → `compressing` → `completed` / `failed` |
| progress | int | 进度 0–100 |
| remainingTime | int | 预计剩余秒数（含排队时间） |
| processingStartedAt | datetime | 开始处理时间（转为 processing 时写入），nullable |
| createdAt | datetime | 创建时间（UTC） |
| updatedAt | datetime | 更新时间（UTC） |
| completedAt | datetime | 完成时间，nullable |
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

Stub 模式四阶段：
```
initializing (0%)
  → extracting (10%-25%, ~2s)
  → colmap (30%-45%, ~3s)
  → training (50%-80%, ~7s)
  → compressing (85%-95%, ~3s)
  → completed (100%)
```

外部算法模式（`ALG_ENABLED=true`）：按 scene 路由
```
commodity → commodity_algorithm（~360s 预期）
indoor / outdoor → external_algorithm（~960s 预期）
```
两算法任务内部通过 Docker SDK 运行外部容器，阻塞等待退出后 inline 调用 `finalize_outputs` 输出终化。无中间进度阶段明细。超时阈值按 scene 区分：commodity 1800s，其他 3600s。

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

| 条件 | 阈值 | 操作 | 执行方式 |
|------|------|------|---------|
| status=pending 超时未启动 | 24h（可配置） | 删除 DB 记录 | M1 Beat → Redis → 任意 Worker |
| status=processing 超时无更新 | 按 scene 计算（5分钟检测） | 标记为 failed | M1 Beat → Redis → 任意 Worker |
| status=completed/failed 超时 | 30d（可配置） | 删除 DB 记录 | M1 Beat → Redis → 任意 Worker |
| 本地文件（completed/failed） | 7d（可配置） | 删除本地磁盘文件及 MinIO 对象，pending/processing 不清理 | 每个 Worker 进程内嵌守护线程 |

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

通过 `ALG_ENABLED=true` 切换，按 scene 字段路由到不同算法：

```
Worker (Celery task)
  └─ pipeline.py 查 DB 获 task.scene
      ├─ scene=commodity → commodity_algorithm
      │   └─ docker run alg2_image → bash -c " ... python test.py -d /data/tasks/{id} ..."
      │       └─ -v /data/3dgs:/data（两算法共用宿主机目录）
      │   └─ 阻塞等待退出 → UserData/ 下搜 recon_result.ply
      │   └─ 找到后 inline 调用 finalize_outputs（复制/压缩/上传/写DB）→ completed
      └─ 其他 scene → external_algorithm
          └─ docker run alg_image → python alg_script --input_dir /data/tasks/{id} --output_dir ...
              └─ -v /data/3dgs:/data
          └─ 阻塞等待退出 → 搜 point_cloud.ply
          └─ 找到后 inline 调用 finalize_outputs → completed
```

配置项：

| 配置项 | 说明 |
|--------|------|
| `ALG_ENABLED` | 模式开关 |
| `ALG_IMAGE` | 算法 1 Docker 镜像 |
| `ALG_SCRIPT` | 算法 1 入口脚本 |
| `ALG_OUTPUT_DIR` | 算法 1 输出子目录 |
| `ALG_PLY_NAME` | 算法 1 PLY 文件名 |
| `ALG_PLY_SUBDIR` | 算法 1 PLY 搜索路径 |
| `ALG_HOST_DATA_DIR` | 宿主机数据目录 |
| `ALG_EXPECTED_SECONDS` | 算法 1 预计执行时间（秒） |
| `ALG_MAX_SECONDS` | 算法 1 最大超时时间（秒） |
| `ALG2_IMAGE` | 算法 2 Docker 镜像 |
| `ALG2_WORK_DIR` | 算法 2 工作目录 |
| `ALG2_SCRIPT` | 算法 2 入口脚本 |
| `ALG2_EXTRA_ARGS` | 算法 2 额外命令行参数 |
| `ALG2_PLY_NAME` | 算法 2 PLY 文件名 |
| `ALG2_PLY_USERDATA_REL` | 算法 2 PLY 搜索相对路径 |
| `ALG2_PLY_SUBDIR_PREFIX` | 算法 2 PLY 子目录前缀 |
| `ALG2_EXPECTED_SECONDS` | 算法 2 预计执行时间（秒） |
| `ALG2_MAX_SECONDS` | 算法 2 最大超时时间（秒） |
| `ALG2_SHM_SIZE` | 算法 2 共享内存大小 |

完整接口契约见 `docs/openapi.yaml`，数据库设计见 `docs/database_design.md`。
