import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.app.config.settings import settings
from src.app.observability.logging import get_logger

logger = get_logger("database")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_engine_loop: asyncio.AbstractEventLoop | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_factory, _engine_loop
    current_loop: asyncio.AbstractEventLoop | None = None
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _engine is not None and current_loop is not None and _engine_loop is not None and _engine_loop is not current_loop:
        try:
            _engine.sync_engine.dispose()
        except Exception:
            pass
        _engine = None
        _session_factory = None

    if _engine is None:
        _engine_loop = current_loop
        db_url = settings.get_asyncpg_database_url()
        # Clean logging of DB connection without secrets
        safe_url = db_url.split("@")[-1] if "@" in db_url else "local"
        logger.info(f"Initializing Async Database Engine for target: {safe_url}")

        connect_args: dict[str, Any] = {
            "server_settings": {
                "search_path": f"{settings.POSTGRES_SCHEMA},public",
                "client_encoding": "UTF8",
            }
        }
        if settings.POSTGRES_SSLMODE == "require":
            connect_args["ssl"] = "require"

        _engine = create_async_engine(
            db_url,
            echo=(settings.LOG_LEVEL.upper() == "DEBUG"),
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_pre_ping=settings.DB_POOL_PRE_PING,
            pool_use_lifo=True,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_health() -> bool:
    """Performs a lightweight query to verify database health."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1;"))
            val = result.scalar()
            return val == 1
    except Exception as e:  # noqa: BLE001 - health check must never crash startup
        logger.error(f"Database health check failed: {e}")
        return False


async def close_db_engine() -> None:
    global _engine, _session_factory, _engine_loop
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        _engine_loop = None
        logger.info("Database engine connections disposed.")
