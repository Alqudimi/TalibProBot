from datetime import UTC, datetime

from sqlalchemy import update

from src.app.infrastructure.database.session import get_session_factory
from src.app.modules.accounts.models import User
from src.app.observability.logging import get_logger

from .celery_app import celery_app

logger = get_logger("tasks")


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_kwargs={"max_retries": 5},
)
def persist_user_heartbeat(self, user_id: str) -> str:
    """Persist activity outside the Telegram response path."""
    import asyncio

    asyncio.run(_persist_heartbeat_with_factory(user_id))
    return user_id


async def _persist_heartbeat_with_factory(user_id: str) -> None:
    async with get_session_factory()() as session:
        await _persist_heartbeat(session, user_id)
        await session.commit()


async def _persist_heartbeat(session, user_id: str) -> None:
    import uuid

    await session.execute(
        update(User)
        .where(User.user_id == uuid.UUID(user_id))
        .values(last_seen_at=datetime.now(UTC))
    )
