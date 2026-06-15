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

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

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

    # Auth
    api_key: str = Field(default="")

    # Task lifecycle
    task_pending_ttl_hours: int = Field(default=24)
    task_completed_ttl_days: int = Field(default=7)

    # Pipeline defaults
    default_fps: int = Field(default=5)
    default_iterations: int = Field(default=30000)

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

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
                raise ValueError(f"无效输出类型 '{t}'，支持: {VALID_OUTPUT_TYPES}")
        return v


settings = Settings()

# 任务输出目录（跨层共享的配置常量）
TASK_OUTPUT_DIR = os.path.join(settings.local_storage_dir, "tasks")
