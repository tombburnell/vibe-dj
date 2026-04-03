from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from track_mapper_api.config import get_database_url

_async_engine = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def _to_async_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+psycopg_async://", 1)
    if url.startswith("sqlite+pysqlite:"):
        return url.replace("sqlite+pysqlite:", "sqlite+aiosqlite:", 1)
    raise RuntimeError(
        "DATABASE_URL must use postgresql+psycopg:// or sqlite+pysqlite:// for async I/O. "
        f"Got scheme: {url.split(':', 1)[0]}"
    )


def _make_async_engine():
    url = _to_async_url(get_database_url())
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    return create_async_engine(url, **kwargs)


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        _async_engine = _make_async_engine()
    return _async_engine


def reset_engine() -> None:
    """Test hook: dispose and clear cached async engine/session factory."""
    global _async_engine, _AsyncSessionLocal
    eng = _async_engine
    _async_engine = None
    _AsyncSessionLocal = None
    if eng is not None:
        try:
            asyncio.run(eng.dispose())
        except RuntimeError:
            pass


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            get_async_engine(),
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield one AsyncSession per request; commit on success, rollback on error."""
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
