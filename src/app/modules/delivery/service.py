import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.modules.delivery.models import Delivery, DeliveryAttempt
from src.app.observability.logging import get_logger

logger = get_logger("delivery")


class DeliveryService:
    """Service managing asset deliveries, idempotency, and delivery attempts."""

    @staticmethod
    async def create_delivery(
        session: AsyncSession,
        asset_id: uuid.UUID,
        idempotency_key: str,
        order_item_id: Optional[uuid.UUID] = None,
        service_request_id: Optional[uuid.UUID] = None,
        expires_at: Optional[datetime] = None,
    ) -> Delivery:
        """Creates or retrieves an idempotent delivery record."""
        stmt = select(Delivery).where(Delivery.idempotency_key == idempotency_key)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

        delivery = Delivery(
            id=uuid.uuid4(),
            asset_id=asset_id,
            order_item_id=order_item_id,
            service_request_id=service_request_id,
            idempotency_key=idempotency_key,
            status="queued",
            available_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )
        session.add(delivery)
        await session.flush()
        logger.info(f"Created delivery {delivery.id} for asset {asset_id} (key {idempotency_key})")
        return delivery

    @staticmethod
    async def record_delivery_attempt(
        session: AsyncSession,
        delivery_id: uuid.UUID,
        channel: str = "telegram",
        external_message_id: Optional[str] = None,
        success: bool = True,
        error_code: Optional[str] = None,
        error_message_safe: Optional[str] = None,
    ) -> DeliveryAttempt:
        """Records a transmission attempt for a delivery."""
        stmt = select(Delivery).where(Delivery.id == delivery_id)
        res = await session.execute(stmt)
        delivery = res.scalar_one_or_none()
        if not delivery:
            raise ValueError(f"Delivery {delivery_id} not found.")

        attempt_num = delivery.attempts + 1
        now = datetime.now(timezone.utc)
        delivery.attempts = attempt_num
        delivery.last_attempt_at = now

        if success:
            delivery.status = "delivered"
            if not delivery.first_delivered_at:
                delivery.first_delivered_at = now
        else:
            delivery.status = "failed"

        attempt = DeliveryAttempt(
            id=uuid.uuid4(),
            delivery_id=delivery.id,
            attempt_number=attempt_num,
            channel=channel,
            status="succeeded" if success else "failed",
            external_message_id=external_message_id,
            started_at=now,
            finished_at=now,
            error_code=error_code,
            error_message_safe=error_message_safe,
        )
        session.add(attempt)
        await session.flush()
        return attempt
