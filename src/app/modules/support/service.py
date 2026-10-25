import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.app.modules.support.models import SupportTicket, SupportTicketMessage
from src.app.observability.logging import get_logger

logger = get_logger("support")


class SupportService:
    """Service managing customer helpdesk tickets, escalations, and replies."""

    @staticmethod
    async def create_ticket(
        session: AsyncSession,
        user_id: uuid.UUID,
        subject: str,
        initial_message: str,
        category: str = "technical",
        priority: int = 3,
        related_order_id: Optional[uuid.UUID] = None,
    ) -> SupportTicket:
        ticket = SupportTicket(
            id=uuid.uuid4(),
            user_id=user_id,
            subject=subject,
            category=category,
            priority=priority,
            related_order_id=related_order_id,
            status="open",
        )
        session.add(ticket)
        await session.flush()

        msg = SupportTicketMessage(
            id=uuid.uuid4(),
            ticket_id=ticket.id,
            sender_user_id=user_id,
            sender_kind="customer",
            body=initial_message,
        )
        session.add(msg)
        await session.flush()
        logger.info(f"Opened support ticket #{ticket.id} for user {user_id}")
        return ticket

    @staticmethod
    async def get_user_tickets(session: AsyncSession, user_id: uuid.UUID) -> List[SupportTicket]:
        stmt = (
            select(SupportTicket)
            .options(selectinload(SupportTicket.messages))
            .where(SupportTicket.user_id == user_id)
            .order_by(SupportTicket.created_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
