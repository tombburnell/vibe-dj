from __future__ import annotations

import asyncio
import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from track_mapper_api.config import clear_config_cache
from track_mapper_api.db.session import reset_engine
from track_mapper_api.deps import get_db
from track_mapper_api.main import app
from track_mapper_api.models import Base


@pytest.fixture(autouse=True)
def _sqlite_db() -> None:
    clear_config_cache()
    reset_engine()

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async def init_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_schema())

    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
    reset_engine()
    clear_config_cache()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
