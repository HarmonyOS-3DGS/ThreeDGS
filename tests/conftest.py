"""pytest fixtures for the 3DGS platform."""
import os

# 必须在导入任何 backend 模块前设置环境变量
#（backend.core.database 在导入时会基于 settings 创建引擎）
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")
os.environ.setdefault("MINIO_BUCKET", "gaussian")
os.environ.setdefault("MINIO_SECURE", "false")
os.environ.setdefault("API_KEY", "test-key")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base, get_db, init_db
from backend.api.main import app


# Use SQLite in-memory for tests
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


_original_get_db_override = None


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Session-scoped fixture: 建表 → 注入测试 DB → 测试结束后清理。"""
    global _original_get_db_override

    Base.metadata.create_all(bind=engine)
    init_db()

    # 保存原始依赖并注入测试版本
    _original_get_db_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db

    yield

    # 恢复原始依赖
    if _original_get_db_override is not None:
        app.dependency_overrides[get_db] = _original_get_db_override
    elif get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app, headers={"Authorization": "test-key"})


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
