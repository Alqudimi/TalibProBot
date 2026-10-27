import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.modules.entitlements.models import EntitlementDefinition, EntitlementGrant
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
        duration_days: int = 30,
        entitlement_ids: Optional[List[str]] = None,
        originating_order_item_id: Optional[uuid.UUID] = None,
    ) -> Subscription:
        """Activates a user subscription and issues associated entitlement grants."""
        now = datetime.now(timezone.utc)
        period_end = now + timedelta(days=duration_days)

        if originating_order_item_id:
            existing_stmt = select(Subscription).where(
                Subscription.originating_order_item_id == originating_order_item_id
            )
            existing = (await session.execute(existing_stmt)).scalar_one_or_none()
            if existing:
                return existing

        # Check existing active subscription for this offer
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.plan_offer_id == offer_id,
                Subscription.status == "active",
            )
        )
        result = await session.execute(stmt)
        sub = result.scalar_one_or_none()

        if sub:
            # Extend period
            base_time = sub.current_period_end if sub.current_period_end and sub.current_period_end > now else now
            sub.current_period_end = base_time + timedelta(days=duration_days)
            sub.updated_at = now
            logger.info(f"Subscription {sub.id} extended to {sub.current_period_end}")
        else:
            sub = Subscription(
                id=uuid.uuid4(),
                user_id=user_id,
                plan_offer_id=offer_id,
                originating_order_item_id=originating_order_item_id,
                status="active",
                current_period_start=now,
                current_period_end=period_end,
                started_at=now,
            )
            session.add(sub)
            await session.flush()
            logger.info(f"New subscription {sub.id} activated for user {user_id}")

        # Grant entitlements if specified
        if entitlement_ids:
            for ent_ref in entitlement_ids:
                ent_def = None
                ent_uuid = None
                if isinstance(ent_ref, uuid.UUID):
                    ent_uuid = ent_ref
                elif isinstance(ent_ref, str):
                    try:
                        ent_uuid = uuid.UUID(ent_ref)
                    except ValueError:
                        ent_uuid = None

                if ent_uuid:
                    stmt = select(EntitlementDefinition).where(EntitlementDefinition.id == ent_uuid)
                    ent_def = (await session.execute(stmt)).scalar_one_or_none()

                if not ent_def and isinstance(ent_ref, str):
                    stmt = select(EntitlementDefinition).where(EntitlementDefinition.code == ent_ref)
                    ent_def = (await session.execute(stmt)).scalar_one_or_none()
                    if not ent_def:
                        ent_def = EntitlementDefinition(
                            id=uuid.uuid4(),
                            code=ent_ref,
                            name_ar=ent_ref,
                            unit="access",
                        )
                        session.add(ent_def)
                        await session.flush()

                if ent_def:
                    grant = EntitlementGrant(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        entitlement_id=ent_def.id,
                        status="active",
                        starts_at=now,
                        ends_at=sub.current_period_end,
                        source_subscription_id=sub.id,
                    )
                    session.add(grant)

        await session.flush()
        return sub

    @staticmethod
    async def check_user_entitlement(session: AsyncSession, user_id: uuid.UUID, entitlement_id: str) -> bool:
        """Checks if a user has an active, unexpired grant for a given entitlement."""
        now = datetime.now(timezone.utc)
        ent_uuid = None
        if isinstance(entitlement_id, uuid.UUID):
            ent_uuid = entitlement_id
        elif isinstance(entitlement_id, str):
            try:
                ent_uuid = uuid.UUID(entitlement_id)
            except ValueError:
                ent_uuid = None

        cond = (EntitlementDefinition.code == str(entitlement_id))
        if ent_uuid is not None:
            cond = cond | (EntitlementGrant.entitlement_id == ent_uuid)

        stmt = (
            select(EntitlementGrant)
            .join(EntitlementDefinition, EntitlementDefinition.id == EntitlementGrant.entitlement_id)
            .where(
                EntitlementGrant.user_id == user_id,
                cond,
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

    @staticmethod
    async def get_user_active_subscriptions(session: AsyncSession, user_id: uuid.UUID) -> List[Subscription]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
                (Subscription.current_period_end.is_(None) | (Subscription.current_period_end > now)),
            )
            .order_by(Subscription.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
