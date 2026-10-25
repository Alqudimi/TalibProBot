import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.app.modules.providers.models import ProviderAvailabilityRule, ProviderProfile
from src.app.observability.logging import get_logger

logger = get_logger("providers")


class ProviderService:
    """Service managing tutor and provider profiles, verification status, and availability."""

    @staticmethod
    async def get_or_create_profile(
        session: AsyncSession,
        user_id: uuid.UUID,
        public_name: str,
        headline: Optional[str] = None,
        bio: Optional[str] = None,
    ) -> ProviderProfile:
        stmt = select(ProviderProfile).where(ProviderProfile.user_id == user_id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()
        if not profile:
            profile = ProviderProfile(
                id=uuid.uuid4(),
                user_id=user_id,
                public_name=public_name,
                headline=headline,
                bio=bio,
                verification_status="pending",
                provider_status="inactive",
            )
            session.add(profile)
            await session.flush()
            logger.info(f"Created provider profile {profile.id} for user {user_id}")
        return profile

    @staticmethod
    async def list_active_providers(session: AsyncSession) -> List[ProviderProfile]:
        stmt = (
            select(ProviderProfile)
            .options(selectinload(ProviderProfile.availability_rules))
            .where(ProviderProfile.provider_status == "active")
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
