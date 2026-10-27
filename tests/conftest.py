import asyncio
import os
import uuid
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
# Keep direct black-box/unit test construction independent from a developer's
# placeholder .env. This is a syntactically valid token and is never sent to
# Telegram because tests use mocked transports.
os.environ.setdefault("BOT_TOKEN", "1234567890:pytest_valid_local_token")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5434/academic")
os.environ.setdefault("POSTGRES_SCHEMA", "student_platform")

from src.app.config.settings import settings
import src.app.modules
from src.app.modules.accounts.models import User
from src.app.modules.catalog.models import OfferPrice, ProductOffer, ServiceCategory, ServiceDefinition
from src.app.shared.models import Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated database session for testing."""
    engine = create_async_engine(
        settings.get_asyncpg_database_url(),
        connect_args={
            "server_settings": {
                "search_path": f"{settings.POSTGRES_SCHEMA},public",
                "client_encoding": "UTF8",
            }
        },
    )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()
