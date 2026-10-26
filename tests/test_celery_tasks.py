import uuid

import pytest
from sqlalchemy import select

from src.app.infrastructure.tasks.tasks import _persist_heartbeat
from src.app.modules.accounts.models import User


@pytest.mark.asyncio
async def test_heartbeat_task_persists_with_real_postgres(db_session):
    user = User(
        user_id=uuid.uuid4(),
        display_name="Celery test",
        preferred_language="ar",
        last_seen_at=None,
    )
    user_id = user.user_id
    db_session.add(user)
    await db_session.commit()

    await _persist_heartbeat(db_session, str(user_id))
    await db_session.commit()
    db_session.expire_all()
    refreshed = await db_session.scalar(select(User).where(User.user_id == user_id))
    assert refreshed is not None
    assert refreshed.last_seen_at is not None
