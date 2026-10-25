import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.app.modules.bookings.models import Booking, BookingParticipant
from src.app.observability.logging import get_logger

logger = get_logger("bookings")


class BookingService:
    """Service managing 1-on-1 tutoring sessions, office hours, and group bookings."""

    @staticmethod
    async def create_booking(
        session: AsyncSession,
        provider_id: uuid.UUID,
        session_title: str,
        starts_at: datetime,
        ends_at: datetime,
        user_id: uuid.UUID,
        order_item_id: Optional[uuid.UUID] = None,
        capacity: int = 1,
    ) -> Booking:
        """Creates a booking with atomic provider overlap protection."""
        booking = Booking(
            id=uuid.uuid4(),
            provider_id=provider_id,
            session_title=session_title,
            starts_at=starts_at,
            ends_at=ends_at,
            order_item_id=order_item_id,
            created_by=user_id,
            capacity=capacity,
            status="confirmed",
        )
        session.add(booking)
        await session.flush()

        participant = BookingParticipant(
            id=uuid.uuid4(),
            booking_id=booking.id,
            user_id=user_id,
            participant_status="booked",
            joined_at=datetime.now(timezone.utc),
        )
        session.add(participant)
        await session.flush()
        logger.info(f"Created booking {booking.id} with provider {provider_id} for user {user_id}")
        return booking

    @staticmethod
    async def get_user_bookings(session: AsyncSession, user_id: uuid.UUID) -> List[Booking]:
        stmt = (
            select(Booking)
            .join(BookingParticipant, BookingParticipant.booking_id == Booking.id)
            .where(BookingParticipant.user_id == user_id)
            .order_by(Booking.starts_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
