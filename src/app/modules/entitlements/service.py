import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.modules.entitlements.models import EntitlementDefinition, EntitlementGrant, EntitlementUsageBucket
from src.app.observability.logging import get_logger

logger = get_logger("entitlements")


class EntitlementService:
    """Service managing feature entitlement verification, grants, and atomic quota consumption."""

    @staticmethod
    async def grant_entitlement_for_order(
        session: AsyncSession,
        user_id: uuid.UUID,
        entitlement_code: str,
        source_order_item_id: uuid.UUID,
        service_id: Optional[uuid.UUID] = None,
        ends_at: Optional[datetime] = None,
        limit_amount: Optional[int] = None,
    ) -> EntitlementGrant:
        """Grants an entitlement to a user resulting from an order item."""
        stmt = select(EntitlementDefinition).where(EntitlementDefinition.code == entitlement_code)
        res = await session.execute(stmt)
        definition = res.scalar_one_or_none()
        if not definition:
            raise ValueError(f"Entitlement '{entitlement_code}' definition not found.")

        grant = EntitlementGrant(
            id=uuid.uuid4(),
            entitlement_id=definition.id,
            user_id=user_id,
            source_order_item_id=source_order_item_id,
            service_id=service_id,
            status="active",
            ends_at=ends_at,
            limit_amount=limit_amount,
        )
        session.add(grant)
        await session.flush()
        logger.info(f"Granted entitlement '{entitlement_code}' to user {user_id} (grant {grant.id})")
        return grant

    @staticmethod
    async def check_access(session: AsyncSession, user_id: uuid.UUID, entitlement_code: str) -> bool:
        """Checks if a user has an active grant for the given entitlement."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(EntitlementGrant)
            .join(EntitlementDefinition, EntitlementDefinition.id == EntitlementGrant.entitlement_id)
            .where(
                EntitlementGrant.user_id == user_id,
                EntitlementDefinition.code == entitlement_code,
                EntitlementGrant.status == "active",
                EntitlementGrant.starts_at <= now,
                (EntitlementGrant.ends_at.is_(None)) | (EntitlementGrant.ends_at > now),
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none() is not None
