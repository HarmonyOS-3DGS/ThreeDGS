# 3DGS 训练平台 — 开发者接口文档

> 本文档面向外部开发者，说明如何通过 REST API 提交和管理 3DGS 训练任务。

---

## 平台简介

本平台提供 3D Gaussian Splatting（3DGS）端到端训练服务。开发者上传视频文件，平台自动完成训练并输出 3D 场景模型文件（PLY）。

### 适用场景

| 场景 | 参数值 | 说明 |
|------|--------|------|
| 商品展示 | `commodity` | 适用于电商商品的三维重建 |
| 室内场景 | `indoor` | 适用于室内空间扫描重建 |
| 室外场景 | `outdoor` | 适用于室外大场景重建 |

### 完整流程

```
开发者系统                    3DGS 平台
    │                                │
    │  POST /auth/token              │  ── 获取 JWT
    │◄───────── access_token ────────┤
    │                                │
    │  POST /tasks                   │  ── 提交视频元数据
    │◄─── taskId + uploadInfos ──────┤
    │                                │
    │  PUT uploadUrl                 │  ── 上传视频文件
    │◄────────── 200 OK ────────────┤
    │                                │
    │  POST /tasks/{id}/start        │  ── 启动流水线
    │◄─────── remainingTime ─────────┤
    │                                │
    │  GET /tasks/{id} (轮询)        │  ── 查询状态
    │◄──── progress/status ──────────┤
    │                                │
    │  GET /tasks/{id}               │  ── 查询下载 URL
    │◄──── downloadInfos ────────────┤
    │                                │
    │  GET downloadUrl               │  ── 下载模型文件
    │◄──────── 文件流 ───────────────┤
```

---

## 目录

1. [前置条件](#1-前置条件)
2. [接口概览](#2-接口概览)
3. [获取 Token](#3-获取-token)
4. [创建任务](#4-创建任务)
5. [启动任务](#5-启动任务)
6. [查询任务状态](#6-查询任务状态)
7. [完整流程示例](#7-完整流程示例)
8. [字段值约束](#8-字段值约束)
9. [响应格式与错误码](#9-响应格式与错误码)

---

## 1. 前置条件

### 1.1 服务器地址

```
https://<服务器域名或IP>
```

### 1.2 公共 Header

所有请求需携带以下 Header：

| Header | 说明 | 约束 | 示例 |
|--------|------|------|------|
| `projectId` | 项目标识，从 AGC 创建项目获取。当前为预留值，未做校验 | 最长 20 字符 | `project-01` |
| `Authorization` | Bearer JWT Token（见 [获取 Token](#3-获取-token)） | — | `Bearer eyJ...` |

---

## 2. 接口概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/token` | 获取 JWT Token，用于接口鉴权 |
| POST | `/tasks` | 创建任务，返回上传 URL |
| POST | `/tasks/{taskId}/start` | 启动训练任务 |
| GET | `/tasks/{taskId}` | 查询任务状态 |

---

## 3. 获取 Token

获取 JWT 访问凭证，用于后续接口鉴权。

### 请求

```http
POST /auth/token
Authorization: Basic base64(<client_id>:<secret>)
```

### 响应

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 字段说明

| 字段 | 说明 | 约束 |
|------|------|------|
| `access_token` | JWT Token，后续请求携带 `Authorization: Bearer <token>` | 算法 HS256 |
| `token_type` | Token 类型 | 值为 `bearer` |
| `expires_in` | 有效期 | 单位：秒，过期后需重新获取 |

### 示例

```bash
curl -X POST https://<server>/auth/token \
  -H "Authorization: Basic $(echo -n 'your-client-id:your-secret' | base64)"
```

> - `clientId` 和 `clientSecret` 由平台分发提供
> - 当前 Token 仅用于接口鉴权。后续将接入 AGC（AppGallery Connect）实现项目级鉴权，届时鉴权方式可能调整
> - Token 有效期 1 小时。长时间训练（>1 小时）需在过期前重新获取 Token 并重试请求

---

## 4. 创建任务

创建一个 3DGS 训练任务，提交视频元数据，返回预签名上传 URL。

### 请求

```http
POST /tasks
Content-Type: application/json
Authorization: Bearer <JWT>
projectId: <项目标识>
```

```json
{
  "externalCode": "EXT-001",
  "fileInfos": [
    {
      "fileName": "scene.mp4",
      "sha256": "abc123...",
      "contentLength": 1048576,
      "fileUrl": "",
      "fileRole": "source_video",
      "mimeType": "video/mp4"
    }
  ],
  "scene": "indoor"
}
```

**请求字段说明：**

| 字段 | 类型 | 必填 | 说明 | 约束 |
|------|------|------|------|------|
| `externalCode` | string | 是 | 外部系统唯一编号 | 最长 256 字符 |
| `scene` | string | 是 | 场景类型 | 取值 `commodity` / `indoor` / `outdoor` |
| `fileInfos` | array | 是 | 文件信息列表 | 最少 1 项，最多 3 项 |
| `fileInfos[].fileName` | string | 是 | 原始文件名（含后缀） | 最长 256 字符 |
| `fileInfos[].sha256` | string | 否 | 文件 SHA256 哈希 | 最长 64 字符 |
| `fileInfos[].contentLength` | int | 否 | 文件大小 | 单位：字节 |
| `fileInfos[].fileUrl` | string | 否 | 预留字段，传空串 | 最长 1024 字符 |
| `fileInfos[].fileRole` | string | 否 | 文件角色 | 默认为 `source_video`，输入文件仅支持此值 |
| `fileInfos[].mimeType` | string | 否 | MIME 类型 | 最长 128 字符 |

### 响应

```json
{
  "ret": {"code": 0, "msg": "success"},
  "taskId": "332011480592384",
  "uploadInfos": [
    {
      "objectId": "scene.mp4",
      "fileName": "scene.mp4",
      "url": "https://storage-server/presigned-url?...",
      "method": "PUT",
      "headers": {
        "Content-Type": "video/mp4"
      }
    }
  ]
}
```

**响应字段说明：**

| 字段 | 说明 | 约束 |
|------|------|------|
| `taskId` | 任务 ID | — |
| `uploadInfos` | 文件上传信息列表，每个元素包含上传 URL | — |
| `uploadInfos[].objectId` | 对象 ID（文件名，不含路径前缀） | — |
| `uploadInfos[].fileName` | 文件名 | — |
| `uploadInfos[].url` | 文件访问地址 | 预签名 URL 或 API 端点 |
| `uploadInfos[].method` | HTTP 请求方法 | 取值 `PUT` / `GET` |
| `uploadInfos[].headers` | 请求所需的额外 HTTP 头信息 | — |

### 上传文件

拿到 `uploadInfos` 后，按返回的 `url` 和 `headers` 逐项上传文件：

```bash
# 单文件上传示例（多文件时同理）
curl -X PUT "<uploadInfos[].url>" \
  -H "Content-Type: video/mp4" \
  --data-binary @scene.mp4
```

> ⚠️ 上传时必须携带返回的 `headers` 中的 Content-Type，否则服务端可能拒绝请求。视频文件上传后还会校验文件头魔数，声明为 `source_video` 但实际非视频文件将被拒绝（HTTP 400）。

---

## 5. 启动任务

文件上传完成后，调用启动接口触发训练流水线。

### 请求

```http
POST /tasks/{taskId}/start
Authorization: Bearer <JWT>
projectId: <项目标识>
```

### 响应

```json
{
  "ret": {"code": 0, "msg": "success"},
  "remainingTime": 120
}
```

| 字段 | 说明 |
|------|------|
| `remainingTime` | 预估剩余秒数（含排队时间） |

> ⚠️ 调用前确保文件已上传。若文件未上传，返回 HTTP 400。

---

## 6. 查询任务状态

### 请求

```http
GET /tasks/{taskId}
Authorization: Bearer <JWT>
projectId: <项目标识>
```

### 响应

```json
{
  "ret": {"code": 0, "msg": "success"},
  "taskId": "332011480592384",
  "status": "processing",
  "remainingTime": 85,
  "scene": "indoor",
  "errorMessage": "",
  "downloadInfos": []
}
```

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| `taskId` | string | 任务 ID | Snowflake 纯数字递增 |
| `status` | string | 任务状态 | 取值 `pending` / `processing` / `completed` / `failed` |
| `remainingTime` | int | 预估剩余秒数 | — |
| `scene` | string | 场景类型 | 取值 `commodity` / `indoor` / `outdoor` |
| `errorMessage` | string | 失败时的错误信息 | — |
| `downloadInfos` | array | 可下载文件列表（完成后非空） | 每项为预签名下载 URL |

**任务状态说明：**

| 状态 | 含义 |
|------|------|
| `pending` | 任务已创建，等待启动 |
| `processing` | 训练流水线正在执行 |
| `completed` | 执行成功，可下载输出文件 |
| `failed` | 执行失败，查看 `errorMessage` 获取原因 |

**完成后 `downloadInfos` 示例：**

```json
"downloadInfos": [
  {
    "objectId": "model.ply",
    "fileName": "model.ply",
    "url": "https://storage-server/...",
    "method": "GET"
  }
]
```

### 下载输出文件

任务状态变为 `completed` 后，可通过 `downloadInfos` 中的 URL 下载输出文件。

> ⚠️ 支持 Query 参数传递 JWT（浏览器兼容）：
> ```
> GET /tasks/{taskId}/download/model.ply?projectId=<项目标识>&Authorization=Bearer%20<JWT>
> ```



---

## 7. 完整流程示例

### 7.1 curl 脚本

```bash
#!/bin/bash
SERVER="https://<服务器域名>"
CLIENT_ID="your-client-id"
SECRET="your-secret"
PROJECT="project-01"

# Step 1: 获取 JWT
JWT=$(curl -s -X POST "$SERVER/auth/token" \
  -H "Authorization: Basic $(echo -n "$CLIENT_ID:$SECRET" | base64)" \
  | jq -r '.access_token')

# Step 2: 创建任务
CREATE_RSP=$(curl -s -X POST "$SERVER/tasks" \
  -H "Authorization: Bearer $JWT" \
  -H "projectId: $PROJECT" \
  -H "Content-Type: application/json" \
  -d '{
    "externalCode": "DEMO-001",
    "fileInfos": [{"fileName": "demo.mp4","sha256":"","contentLength":0,"fileUrl":"","fileRole":"source_video","mimeType":"video/mp4"}],
    "scene": "indoor"
  }')

TASK_ID=$(echo $CREATE_RSP | jq -r '.taskId')

echo "Task created: $TASK_ID"

# Step 3: 上传文件（遍历所有 uploadInfos）
UPLOAD_COUNT=$(echo $CREATE_RSP | jq '.uploadInfos | length')
for i in $(seq 0 $((UPLOAD_COUNT - 1))); do
  UPLOAD_URL=$(echo $CREATE_RSP | jq -r ".uploadInfos[$i].url")
  curl -X PUT "$UPLOAD_URL" \
    -H "Content-Type: video/mp4" \
    --data-binary @demo.mp4
done

# Step 4: 启动任务
curl -s -X POST "$SERVER/tasks/$TASK_ID/start" \
  -H "Authorization: Bearer $JWT" \
  -H "projectId: $PROJECT"

echo "Task started, polling status..."

# Step 5: 轮询直至完成
while true; do
  STATUS_RSP=$(curl -s "$SERVER/tasks/$TASK_ID" \
    -H "Authorization: Bearer $JWT" \
    -H "projectId: $PROJECT")
  STATUS=$(echo $STATUS_RSP | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 5
done

# Step 6: 下载输出文件
echo $STATUS_RSP | jq -r '.downloadInfos[] | .fileName + " -> " + .url'
```

### 7.2 时序图

```
开发者系统                    3DGS 平台
    │                            │
    │  POST /auth/token          │  ── 获取 JWT
    │◄───────── access_token ────┤
    │                            │
    │  POST /tasks               │  ── 提交视频元数据
    │◄─── taskId + uploadInfos ──┤
    │                            │
    │  PUT uploadUrl             │  ── 上传视频文件
    │◄────────── 200 OK ────────┤
    │                            │
    │  POST /tasks/{id}/start    │  ── 启动流水线
    │◄────── remainingTime ─────┤
    │                            │
    │  GET /tasks/{id} (轮询)    │  ── 查询状态
    │◄─── status/progress ──────┤
    │                            │
    │  GET /tasks/{id}           │  ── 查询下载 URL
    │◄─── downloadInfos ────────┤
    │                            │
    │  GET downloadUrl           │  ── 下载模型文件
    │◄─────── 文件流 ───────────┤
```

---

## 8. 字段值约束

| 字段 | 约束 |
|------|------|
| `projectId`（Header） | 最长 20 字符 |
| `externalCode` | 最长 256 字符 |
| `fileName` | 最长 256 字符 |
| `scene` | 枚举值：`commodity`、`indoor`、`outdoor` |
| `fileInfos` | 最少 1 项，最多 3 项 |
| `fileRole` | 输入文件固定为 `source_video` |
| `sha256` | 最长 64 字符 |
| `fileUrl` | 最长 1024 字符 |
| `mimeType` | 最长 128 字符 |

---

## 9. 响应格式与错误码

所有 API 响应均包含统一包裹结构：

```json
{
  "ret": {"code": 0, "msg": "success"},
  ...
}
```

| ret.code | 含义 |
|----------|------|
| 0 | 成功 |
| 非 0 | 错误，见 `ret.msg` |

### HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 请求成功 |
| 400 | 参数错误或业务逻辑错误 |
| 401 | 鉴权失败 |
| 404 | 任务/文件不存在 |
| 422 | 缺少必填参数 |
| 500 | 服务端内部错误 |

### 业务错误码

| 场景 | HTTP 状态码 | 说明 |
|------|------------|------|
| 文件未上传 | 400 | 启动任务时检测到文件未上传 |
| 任务状态不正确 | 400 | 启动非 pending 状态的任务 |
| 文件已存在 | 400 | 重复上传同一文件 |
| MIME 类型不匹配 | 400 | 上传文件类型与声明的角色不符 |
| 鉴权凭证无效 | 401 | JWT 过期或签名错误 |
| 任务/文件不存在 | 404 | 指定的资源不存在 |
| 缺少必填参数 | 422 | 请求缺少 `projectId` 等必填字段 |
