import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.app.modules.opportunities.models import Opportunity, OpportunityApplication, SavedOpportunity
from src.app.observability.logging import get_logger

logger = get_logger("opportunities")


class OpportunityService:
    """Service managing scholarships, internships, competitions, and student applications tracker."""

    @staticmethod
    async def list_published(
        session: AsyncSession,
        type_id: Optional[int] = None,
        level: Optional[str] = None,
        limit: int = 20,
    ) -> List[Opportunity]:
        stmt = (
            select(Opportunity)
            .options(selectinload(Opportunity.type_rel))
            .where(Opportunity.status == "published")
        )
        if type_id is not None:
            stmt = stmt.where(Opportunity.type_id == type_id)
        if level is not None:
            stmt = stmt.where(Opportunity.level == level)
        stmt = stmt.order_by(Opportunity.deadline_at.asc().nulls_last()).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def save_opportunity(
        session: AsyncSession,
        user_id: uuid.UUID,
        opportunity_id: uuid.UUID,
        user_note: Optional[str] = None,
    ) -> SavedOpportunity:
        saved = SavedOpportunity(user_id=user_id, opportunity_id=opportunity_id, user_note=user_note)
        session.add(saved)
        await session.flush()
        logger.info(f"User {user_id} saved opportunity {opportunity_id}")
        return saved

    @staticmethod
    async def list_user_saved(session: AsyncSession, user_id: uuid.UUID) -> List[Opportunity]:
        stmt = (
            select(Opportunity)
            .join(SavedOpportunity, SavedOpportunity.opportunity_id == Opportunity.id)
            .where(SavedOpportunity.user_id == user_id)
            .order_by(SavedOpportunity.saved_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
