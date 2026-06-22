"""Application configuration using Pydantic Settings."""

import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

VALID_OUTPUT_TYPES = {"raw_model", "spz", "sog"}
COMPRESSIBLE_FORMATS = {"spz", "sog"}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(default="sqlite:///./3dgs.db")

    # MinIO
    minio_endpoint: str = Field(default="localhost:9000")
    minio_public_endpoint: str = Field(default="")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket: str = Field(default="gaussian")
    minio_secure: bool = Field(default=False)

    # Local storage fallback
    use_local_storage: bool = Field(default=False)
    local_storage_dir: str = Field(default="./local_storage")

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # Celery
    celery_broker_url: str = Field(default="memory://")
    celery_result_backend: str = Field(default="cache+memory://")

    # Auth — ServiceAccount 凭证对（逗号分隔 client_id:secret）
    service_accounts_raw: str = Field(default="", alias="SERVICE_ACCOUNTS")
    jwt_secret_key: str = Field(default="")
    jwt_expire_seconds: int = Field(default=3600)
    admin_client_id: str = Field(default="")

    # Task lifecycle
    task_pending_ttl_hours: int = Field(default=24)
    task_completed_ttl_days: int = Field(default=7)

    # Pipeline defaults
    default_fps: int = Field(default=5)
    default_iterations: int = Field(default=30000)

    # Worker 数量（用于排队时间估算）
    worker_count: int = Field(default=1, alias="WORKER_COUNT")

    # 输出类型选择
    output_types: list[str] = Field(default=["raw_model"])

    # 外部算法（一体化模式）
    alg_enabled: bool = Field(default=False)
    alg_image: str = Field(default="alg_pipeline")
    alg_script: str = Field(default="alg_pipeline.pyc")
    alg_output_dir: str = Field(default="output")
    alg_ply_name: str = Field(default="point_cloud.ply")
    alg_ply_subdir: str = Field(default="gaussian_splatting/out/train/grid_0_0/point_cloud")
    alg_expected_seconds: int = Field(default=960)
    alg_max_seconds: int = Field(default=3600)
    alg_host_data_dir: str = Field(default="/data/3dgs")

    # 外部算法 2（commodity 场景专用）
    alg2_image: str = Field(default="alg_image:v1")
    alg2_work_dir: str = Field(default="/data/dist_so")
    alg2_script: str = Field(default="test.py")
    alg2_extra_args: str = Field(default="-s -m 6 --video_mode")
    alg2_ply_name: str = Field(default="recon_result.ply")
    alg2_ply_userdata_rel: str = Field(default="dist_so/UserData")
    # 算法内部取输入路径最后两层目录名拼接成子目录名：test_task_id_{dir1}_{dir2}
    # 当前输入 /data/tasks/{task_id} → dir1=tasks, dir2={task_id} → "test_task_id_tasks_{task_id}"
    alg2_ply_subdir_prefix: str = Field(default="test_task_id_tasks_")
    alg2_expected_seconds: int = Field(default=360)  # 6 分钟
    alg2_max_seconds: int = Field(default=1800)  # 30 分钟超时
    alg2_shm_size: str = Field(default="64g")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @field_validator("output_types", mode="before")
    @classmethod
    def _split_list(cls, v):
        """支持环境变量传入逗号分隔字符串（如 `OUTPUT_TYPES=raw_model,spz,sog`）。"""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @field_validator("output_types")
    @classmethod
    def _validate_output_types(cls, v):
        for t in v:
            if t not in VALID_OUTPUT_TYPES:
                raise ValueError(f"invalid output type '{t}', valid: {VALID_OUTPUT_TYPES}")
        return v

    @property
    def service_accounts(self) -> dict[str, str]:
        """将 SERVICE_ACCOUNTS 字符串解析为 {client_id: secret} 字典。"""
        return parse_service_accounts(self.service_accounts_raw)


def parse_service_accounts(raw: str) -> dict[str, str]:
    """解析 SERVICE_ACCOUNTS 字符串为 {client_id: secret} 字典。"""
    if not raw:
        return {}
    pairs = [x.strip() for x in raw.split(",") if x.strip()]
    result = {}
    for p in pairs:
        if ":" in p:
            cid, secret = p.split(":", 1)
            result[cid.strip()] = secret.strip()
    return result


settings = Settings()

# 任务输出目录（跨层共享的配置常量）
TASK_OUTPUT_DIR = os.path.join(settings.local_storage_dir, "tasks")
