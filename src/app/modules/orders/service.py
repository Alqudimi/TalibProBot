import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.app.modules.catalog.models import OfferPrice, ProductOffer
from src.app.modules.orders.models import Order, OrderItem
from src.app.observability.logging import get_logger
from src.app.shared.errors import OrderInvalidStateError, ServiceNotFoundError

logger = get_logger("orders")


class OrderService:
    """Service handling order lifecycle, price snapshots, transitions and cancellations."""

    @staticmethod
    async def create_order_from_offer(
        session: AsyncSession,
        user_id: uuid.UUID,
        offer_id: uuid.UUID,
        currency_code: str = "XTR",
        customer_notes: Optional[str] = None,
    ) -> Order:
        """Creates a new order with financial snapshot locking the unit price."""
        # 1. Fetch offer and price
        stmt = (
            select(ProductOffer)
            .options(
                selectinload(ProductOffer.prices),
                selectinload(ProductOffer.primary_service),
            )
            .where(ProductOffer.id == offer_id)
        )
        result = await session.execute(stmt)
        offer = result.scalar_one_or_none()
        if not offer:
            raise ServiceNotFoundError(f"Offer {offer_id} does not exist.")

        # Find price for the requested currency
        price_minor = 0
        matched_price_id = None
        for p in offer.prices:
            if p.currency_code == currency_code and (p.valid_until is None or p.valid_until > datetime.now(timezone.utc)):
                price_minor = p.amount_minor
                matched_price_id = p.id
                break

        # If trial or free
        payment_required = (price_minor > 0)

        # 2. Create Order in draft status first with 0 totals, then transition after items are added
        order = Order(
            id=uuid.uuid4(),
            user_id=user_id,
            status="draft",
            currency_code=currency_code,
            subtotal_minor=0,
            discount_total_minor=0,
            tax_total_minor=0,
            total_minor=0,
            customer_note=customer_notes,
        )
        session.add(order)
        await session.flush()

        # 3. Add order item
        item = OrderItem(
            id=uuid.uuid4(),
            order_id=order.id,
            offer_id=offer.id,
            offer_price_id=matched_price_id,
            service_definition_id=offer.primary_service_id,
            product_title_snapshot=offer.title_ar,
            product_code_snapshot=offer.code,
            currency_code=currency_code,
            quantity=1,
            unit_price_minor=price_minor,
            line_discount_minor=0,
            line_total_minor=price_minor,
            line_metadata={},
        )
        session.add(item)
        await session.flush()
        await session.refresh(order)

        # 4. Transition order from draft -> pending_payment (or paid if free/trial)
        if payment_required:
            order.status = "pending_payment"
        else:
            order.status = "paid"
            order.paid_at = datetime.now(timezone.utc)

        await session.flush()
        logger.info(
            f"Created order {order.id} for user {user_id}: total={order.total_minor} {currency_code}, status={order.status}"
        )
        return order

    @staticmethod
    async def get_order_by_id(session: AsyncSession, order_id: uuid.UUID) -> Optional[Order]:
        stmt = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_orders(session: AsyncSession, user_id: uuid.UUID, limit: int = 10) -> List[Order]:
        stmt = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def cancel_order(session: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID, reason: str = "User cancelled") -> Order:
        order = await OrderService.get_order_by_id(session, order_id)
        if not order:
            raise ServiceNotFoundError(f"Order {order_id} not found.")

        if order.user_id != user_id:
            raise OrderInvalidStateError("You are not authorized to cancel this order.")

        if order.status not in ("draft", "pending_payment"):
            raise OrderInvalidStateError(f"Cannot cancel order in status '{order.status}'.")

        order.status = "cancelled"
        order.cancelled_at = datetime.now(timezone.utc)
        await session.flush()
        logger.info(f"Order {order_id} cancelled by user {user_id}. Reason: {reason}")
        return order

