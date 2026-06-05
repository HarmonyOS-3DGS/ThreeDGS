# 参考指引与后续规划

> 本文档梳理 `reference/` 下的参考资料，映射到当前工程架构，给出后续迭代方向。

---

## 一、参考资料索引

### 1. `3dgs_engineering_guide/` — 工程化实践落地指南

一份 11 章的完整技术选型文档（~50KB），涵盖从算法原理到生产部署的全链路。

| 章节 | 内容 | 对当前工程的价值 |
|------|------|-----------------|
| Ch3: 输入端流水线 | FFmpeg 帧提取参数、COLMAP 质量校验、图片输入处理 | 替换 `preprocessor.py` stub 的参考实现 |
| Ch4: 训练框架对比 | 官方 3DGS / gsplat / splatfacto 对比 | 替换 `trainer.py` stub 的选型依据 |
| Ch5: 格式与压缩 | PLY/SPZ/SOG/KSplat 格式对比、剪枝/量化策略 | 替换 `compressor.py` stub 的技术方案 |
| Ch6: Web 渲染引擎 | Spark / GaussianSplats3D / SuperSplat 选型 | 替换 `viewer.html` 中的 PlayCanvas 占位符 |
| Ch7: 部署架构 | FastAPI + Celery + GPU 资源调度 | Phase 2 架构升级参考 |
| Ch8: 移动端优化 | 锥体裁剪、LOD、PWA | 远期规划 |

附带 5 张 PNG 图表：
- `chart1_framework_comparison.png` — 训练框架选型
- `chart2_web_renderer_comparison.png` — Web 渲染器选型
- `chart3_format_compression.png` — 格式压缩对比
- `chart4_mobile_optimization.png` — 移动端优化方案
- `chart5_deployment_architecture.png` — 部署架构

### 2. `3dgs_roadmap/` — 工程化实施路线图

四阶段约 20 周计划，含风险矩阵、预算、团队配置。

| 阶段 | 周期 | 目标 | 当前进度 |
|------|------|------|---------|
| Phase 0: PoC | 1-2 周 | 单 GPU 工作站验证 | 跳过（直接 MVP） |
| Phase 1: MVP | 3-6 周 | FastAPI + Celery + MinIO + Web Viewer | **当前阶段** —— 基础架构已完成 |
| Phase 2: Beta | 7-12 周 | 多 GPU 调度、压缩管线、监控告警 | 待实施 |
| Phase 3: 生产 | 13-20 周 | K8s、HPA、CDN、RBAC、灾备 | 远期规划 |

### 3. `Kimi_Agent_3D高斯API演示/3dgs-demo/` — 参考 Demo

一个完整的 FastAPI + React + WebGL Viewer 全栈示例，以下模块有直接参考价值：

| 模块 | 文件 | 可借鉴点 |
|------|------|---------|
| JWT 认证 | `auth.py` | JWT + Argon2 + OAuth2 Bearer Token |
| 场景元数据 | `models.py` / `scene_manager.py` | PLY header 解析：高斯数量、SH 阶数、包围盒 |
| React 前端 | `frontend/src/` | TypeScript + Vite + React Router + Axios 拦截器 |
| WebGL 查看器 | `ViewerPage.tsx` | @mkkellogg/gaussian-splats-3d + Three.js 集成 |
| API 设计 | `routers/scenes.py` | 文件上传校验、分页、公开/私有场景 |

---

## 二、当前工程与参考资料的映射

```
当前工程                      参考指引
────────                    ────────
backend/worker/models/
  preprocessor.py  ←──────  3dgs_engineering_guide/Ch3 (FFmpeg + COLMAP)
  trainer.py       ←──────  3dgs_engineering_guide/Ch4 (gsplat/Nerfstudio)
  compressor.py    ←──────  3dgs_engineering_guide/Ch5 (SPZ/SOG 压缩)

frontend/viewer.html ←───── 3dgs_engineering_guide/Ch6 (Web 渲染器选型)
                             Kimi_Agent_Demo/ViewerPage.tsx (gaussian-splats-3d)

backend/api/       ←──────  Kimi_Agent_Demo/routers/ (JWT 鉴权可借鉴)
backend/core/      ←──────  Kimi_Agent_Demo/models.py (Scene 元数据模型)

docker-compose.yml ←──────  3dgs_engineering_guide/Ch7 (GPU 调度架构)
                             3dgs_roadmap/Phase 2 (多 GPU + 监控)
```

---

## 三、后续迭代规划

### Phase 1 遗留（当前 MVP 待完善）

| 项目 | 说明 | 优先级 |
|------|------|--------|
| 任务列表接口 | 当前无 GET /tasks 列表，前端 status.html 无法使用 | 高 |
| 文件下载接口 | 输出文件（SPZ/SOG）需提供 HTTP 下载端点 | 高 |
| OBS 对象存储 | 目前使用本地文件系统，需切换到 OBS（华为云对象存储） | 中 |
| 文件类型校验 | 上传时仅前端 accept 限制，后端需校验真实 MIME 类型 | 中 |

### Phase 2 规划（参照 roadmap 的 Phase "Internal Beta"）

| 项目 | 参考文档 | 说明 |
|------|---------|------|
| 真实帧提取 | `3dgs_guide/Ch3` | 替换 `Preprocessor.extract_frames()` 为 FFmpeg CLI 调用 |
| 真实 COLMAP | `3dgs_guide/Ch3` | 替换 `Preprocessor.run_colmap()` 为 colmap CLI + GPU 加速 |
| 真实 3DGS 训练 | `3dgs_guide/Ch4` | 替换 `Trainer.train()` 为 gsplat / Nerfstudio |
| 真实压缩 | `3dgs_guide/Ch5` | 替换 `Compressor.compress_*` 为 3dgsconverter / 自定义压缩 |
| Web 3D 查看器 | `3dgs_guide/Ch6` + `Kimi_Demo/ViewerPage` | 替换 PlayCanvas iframe 为 GaussianSplats3D + Three.js |
| JWT 鉴权 | `Kimi_Demo/auth.py` | 从 API Key 升级到 JWT Bearer Token |
| 进度上报细化 | — | 各阶段上报真实进度（非 stub 固定值） |
| GPU 资源调度 | `3dgs_guide/Ch7` | 多 GPU Worker 分配策略 |

### 远期规划（Phase 3+）

| 项目 | 参考文档 |
|------|---------|
| Kubernetes 部署 | `roadmap/Phase 3` |
| Prometheus + Grafana 监控 | `3dgs_guide/Ch9` |
| CDN 分发、RBAC 权限、审计日志 | `roadmap/Phase 3` |
| 移动端 PWA 查看器 | `3dgs_guide/Ch8` |

---

## 四、技术选型决策树（综合参考文档）

```
输入: 视频 → 帧提取(FFmpeg) → COLMAP SfM → 训练(gsplat 推荐) → 压缩(SPZ 推荐) → 渲染(SuperSplat/GaussianSplats3D)

[格式] PLY 输出 ─→ 移动端? → SPZ (压缩率高)
                ─→ Web 端? → SPLAT (加载快) → SPZ (进阶)

[渲染] 轻量级嵌入 → GaussianSplats3D (Three.js)
       完整查看器 → SuperSplat (独立页面)
       移动端    → antimatter15/splat (WebGL 2.0 兼容)
```

---

## 五、参考文件清单

```
reference/
├── 3dgs_engineering_guide/
│   ├── 3dgs_engineering_guide.md        # 完整文档 (~50KB)
│   ├── chart1_framework_comparison.png
│   ├── chart2_web_renderer_comparison.png
│   ├── chart3_format_compression.png
│   ├── chart4_mobile_optimization.png
│   └── chart5_deployment_architecture.png
├── 3dgs_roadmap/
│   ├── 3dgs_roadmap.md                  # 四阶段路线图 (~30KB)
│   ├── roadmap_phases.png
│   └── roadmap_tech_stack.png
└── Kimi_Agent_3D高斯API演示/
    └── 3dgs-demo/                        # 完整参考 Demo
        ├── README.md                     # 项目概述
        ├── IMPLEMENTATION_REPORT.md      # 实现报告
        ├── create_sample.py              # 示例 PLY 生成
        ├── backend/
        │   ├── auth.py                   # JWT 认证
        │   ├── scene_manager.py          # PLY 解析 + CRUD
        │   ├── routers/scenes.py         # 场景 API
        │   └── ...
        └── frontend/
            └── src/pages/ViewerPage.tsx  # WebGL 3D 查看器
```
