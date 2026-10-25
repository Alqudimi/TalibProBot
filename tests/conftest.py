import asyncio
import uuid
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
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
