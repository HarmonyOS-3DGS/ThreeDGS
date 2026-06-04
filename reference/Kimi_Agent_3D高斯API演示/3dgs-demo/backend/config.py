"""
Application configuration using Pydantic Settings.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Security
    SECRET_KEY: str = "3dgs-demo-secret-key-change-in-production-2025"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours for demo
    
    # Database
    DATABASE_URL: str = "sqlite:///./3dgs_demo.db"
    
    # File Storage
    SCENES_DIR: str = "./scenes"
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB max PLY file
    
    # Demo Mode
    DEMO_MODE: bool = True
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
