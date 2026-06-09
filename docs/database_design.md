# 数据库设计文档

> 本文档对应实现代码：`backend/core/database.py`
>
> ⚠️ **代码与文档同步提醒**：修改 `backend/core/database.py` 中的 ORM 模型（字段、类型、约束、关系）后，请同步更新本文档。反之，设计变更也应先在文档中确认。

---

## 概述

使用 **SQLAlchemy 2.0 ORM**，MVP 阶段通过 `init_db()` 自动建表，无 Alembic 迁移脚本。

支持双数据库后端：
- 生产环境：**PostgreSQL**（通过 `DATABASE_URL` 配置）
- 本地开发：**SQLite**（自动设置为 `check_same_thread=False`）

---

## 表结构

### 1. `tasks` — 任务主表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `String(32)` | PK, `_generate_task_id()` | 格式：`timestamp_ms + uuid4_hex[:6]`，如 `1780614692192a3f4c` |
| `project_id` | `String(20)` | NOT NULL, INDEX | 项目 ID，从请求 Header `projectId` 传入 |
| `external_code` | `String(256)` | NOT NULL, INDEX | 外部系统唯一标识码 |
| `scene` | `String(32)` | NOT NULL | 场景类型枚举：`commodity` / `indoor` / `outdoor` |
| `status` | `String(50)` | DEFAULT `'pending'` | 外部状态：`pending` → `processing` → `completed` / `failed` |
| `current_stage` | `String(50)` | DEFAULT `'initializing'` | 内部阶段：`initializing` → `extracting` → `colmap` → `training` → `compressing` → `completed` / `failed` |
| `progress` | `Integer` | DEFAULT `0` | 进度百分比 0–100 |
| `remaining_time` | `Integer` | DEFAULT `0` | 预计剩余秒数（Stub 模式固定 15 秒递减） |
| `created_at` | `DateTime` | DEFAULT `utcnow` | 创建时间（UTC） |
| `updated_at` | `DateTime` | DEFAULT `utcnow`, `onupdate=utcnow` | 更新时间（UTC） |
| `completed_at` | `DateTime` | NULLABLE | 完成时间（UTC） |
| `error_message` | `Text` | NULLABLE | 失败时的错误信息 |

**关系**：`Task.files` → `TaskFile`（一对多，`cascade="all, delete-orphan"`）

---

### 2. `task_files` — 任务关联文件表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `Integer` | PK, AUTO INCREMENT | 自增主键 |
| `task_id` | `String(32)` | FK → `tasks.id`, NOT NULL | 所属任务 ID |
| `fileName` | `String(256)` | NOT NULL | 原始文件名（ORM 中使用驼峰命名） |
| `sha256` | `String(64)` | NOT NULL | 文件 SHA-256 哈希值 |
| `contentLength` | `Integer` | NOT NULL | 文件大小（字节） |
| `fileUrl` | `String(1024)` | NOT NULL | 文件存储路径（本地绝对路径或 MinIO 路径） |
| `fileRole` | `String(50)` | NOT NULL, DEFAULT `'source_video'` | 文件角色：`source_video` / `source_images` / `compressed_model` / `pose_data` |
| `mimeType` | `String(128)` | NULLABLE | MIME 类型，如 `video/mp4`、`image/png` |

**关系**：`TaskFile.task` → `Task`（多对一）

---

## 枚举定义

### `TaskStatus` — 外部状态（对用户暴露）

| 枚举值 | 状态 | 说明 |
|--------|------|------|
| `PENDING` | `pending` | 任务已创建，等待启动 |
| `PROCESSING` | `processing` | 流水线正在执行 |
| `COMPLETED` | `completed` | 全部阶段执行成功 |
| `FAILED` | `failed` | 流水线执行出错 |

### `TaskStage` — 内部阶段

| 枚举值 | 状态 | 说明 | 进度范围 |
|--------|------|------|---------|
| `INITIALIZING` | `initializing` | 等待中 | 0% |
| `EXTRACTING` | `extracting` | 帧提取中 | 10% → 25% |
| `COLMAP` | `colmap` | COLMAP SfM 中 | 30% → 45% |
| `TRAINING` | `training` | 3DGS 训练中 | 50% → 80% |
| `COMPRESSING` | `compressing` | 压缩中 | 85% → 95% |
| `COMPLETED` | `completed` | 完成 | 100% |
| `FAILED` | `failed` | 失败 | - |

### `FileRole` — 文件角色

| 枚举值 | 说明 | 来源 |
|--------|------|------|
| `source_video` | 用户上传的视频 | 前端创建任务 |
| `source_images` | 用户上传的图片集 | 前端创建任务 |
| `compressed_model` | 最终压缩模型输出（SPZ/SOG） | compress 阶段写入 |
| `pose_data` | 用户上传的位姿文件（预留） | 前端创建任务 |

> MVP 阶段仅使用前三个，`pose_data` 和其余角色按需追加。

---

## ER 关系

```
┌──────────────────┐       ┌────────────────────┐
│      tasks       │       │     task_files     │
├──────────────────┤       ├────────────────────┤
│ id (PK)          │──┐    │ id (PK)            │
│ project_id       │  │    │ task_id (FK) ──────┘
│ external_code    │  └─── │ fileName           │
│ scene            │       │ sha256             │
│ status           │       │ contentLength      │
│ current_stage    │       │ fileUrl            │
│ progress         │       │ fileRole           │
│ remaining_time   │       │ mimeType           │
│ created_at       │       └────────────────────┘
└──────────────────┘
```

---

## 数据库初始化

```python
# backend/core/database.py
def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
```

- MVP 阶段无迁移脚本，每次启动自动建表
- 支持幂等执行（`create_all` 仅创建不存在的表）
- 生产环境建议切换到 Alembic 管理迁移

---

## 索引

| 表 | 字段 | 类型 | 说明 |
|----|------|------|------|
| `tasks` | `project_id` | B-tree | 按项目查询任务列表 |
| `tasks` | `external_code` | B-tree | 按外部编码查重和查询 |
| `task_files` | `task_id` | B-tree | 外键关联查询（SQLAlchemy 自动创建） |

---

## 状态流转

```
                    ┌─────────┐
                    │ pending │
                    └────┬────┘
                         │ POST /tasks/{id}/start
                    ┌────▼──────┐
                    │ processing│
                    └────┬──────┘
                         │
               ┌─────────┼──────────┐
               ▼         ▼          ▼
         extracting   colmap    training
               │         │          │
               └─────────┼──────────┘
                         ▼
                    compressing
                         │
               ┌─────────┼──────────┐
               ▼                    ▼
          completed              failed
```

---

## 同步提醒

> **代码位置**：`backend/core/database.py`
>
> 修改上述文件中的 ORM 模型后，必须同步更新本文档的字段表、索引、状态流转等章节。
>
> 常见需要同步的场景：
> - 新增/删除字段 → 更新 `tasks` 或 `task_files` 字段表
> - 修改字段类型或约束 → 更新字段表的类型/约束列
> - 新增/删除表 → 新增对应章节
> - 修改状态枚举 → 更新枚举表和状态流转图
