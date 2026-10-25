import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy import select
from src.app.modules.entitlements.models import EntitlementGrant
from src.app.modules.subscriptions.models import Subscription
from src.app.observability.logging import get_logger

logger = get_logger("subscriptions")


class SubscriptionService:
    """Service handling recurring subscriptions and user entitlement verification."""

    @staticmethod
    async def activate_subscription(
        session: AsyncSession,
        user_id: uuid.UUID,
        offer_id: uuid.UUID,
        currency_code: str,
        price_minor: int,
        duration_days: int = 30,
        entitlement_ids: Optional[List[str]] = None,
    ) -> Subscription:
        """Activates a user subscription and issues associated entitlement grants."""
        now = datetime.now(timezone.utc)
        period_end = now + timedelta(days=duration_days)

        # Check existing active subscription for this offer
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.offer_id == offer_id,
                Subscription.status == "active",
            )
        )
        result = await session.execute(stmt)
        sub = result.scalar_one_or_none()

        if sub:
            # Extend period
            sub.current_period_end = max(sub.current_period_end, now) + timedelta(days=duration_days)
            sub.updated_at = now
            logger.info(f"Subscription {sub.id} extended to {sub.current_period_end}")
        else:
            sub = Subscription(
                id=uuid.uuid4(),
                user_id=user_id,
                offer_id=offer_id,
                status="active",
                currency_code=currency_code,
                recurring_price_minor=price_minor,
                billing_interval="month",
                current_period_start=now,
                current_period_end=period_end,
            )
            session.add(sub)
            await session.flush()
            logger.info(f"New subscription {sub.id} activated for user {user_id}")

        # Grant entitlements if specified
        if entitlement_ids:
            for ent_id in entitlement_ids:
                grant = EntitlementGrant(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    entitlement_id=ent_id,
                    status="active",
                    starts_at=now,
                    ends_at=sub.current_period_end,
                    grant_source_type="subscription",
                    grant_source_id=sub.id,
                )
                session.add(grant)

        await session.flush()
        return sub

    @staticmethod
    async def check_user_entitlement(session: AsyncSession, user_id: uuid.UUID, entitlement_id: str) -> bool:
        """Checks if a user has an active, unexpired grant for a given entitlement."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(EntitlementGrant)
            .where(
                EntitlementGrant.user_id == user_id,
                EntitlementGrant.entitlement_id == entitlement_id,
                EntitlementGrant.status == "active",
                EntitlementGrant.starts_at <= now,
                (EntitlementGrant.ends_at.is_(None) | (EntitlementGrant.ends_at > now)),
            )
        )
        result = await session.execute(stmt)
        grant = result.scalar_one_or_none()
        return grant is not None

    @staticmethod
    async def get_user_subscriptions(session: AsyncSession, user_id: uuid.UUID) -> List[Subscription]:
        stmt = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
