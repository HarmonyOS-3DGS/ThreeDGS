"""Application configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(default="sqlite:///./3dgs.db")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # MinIO
    minio_endpoint: str = Field(default="localhost:9000")
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
