import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.modules.notifications.models import Notification, ScheduledReminder
from src.app.observability.logging import get_logger

logger = get_logger("notifications")


class NotificationService:
    """Service managing multi-channel user alerts, scheduled study reminders, and deduplication."""

    @staticmethod
    async def create_notification(
        session: AsyncSession,
        user_id: uuid.UUID,
        title: str,
        body: str,
        notification_type: str = "order_updates",
        channel: str = "telegram",
        deduplication_key: Optional[str] = None,
        scheduled_at: Optional[datetime] = None,
    ) -> Notification:
        if deduplication_key:
            stmt = select(Notification).where(Notification.deduplication_key == deduplication_key)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                return existing

        notif = Notification(
            id=uuid.uuid4(),
            user_id=user_id,
            notification_type=notification_type,
            channel=channel,
            title=title,
            body=body,
            status="queued",
            deduplication_key=deduplication_key,
            scheduled_at=scheduled_at or datetime.now(timezone.utc),
        )
        session.add(notif)
        await session.flush()
        logger.info(f"Queued notification {notif.id} for user {user_id} ({notification_type})")
        return notif

    @staticmethod
    async def get_user_notifications(
        session: AsyncSession, user_id: uuid.UUID, limit: int = 20
    ) -> List[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
