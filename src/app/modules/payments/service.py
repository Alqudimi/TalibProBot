import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.infrastructure.queue.outbox import enqueue_outbox_event
from src.app.modules.orders.models import Order
from src.app.modules.payments.models import IdempotencyRecord, PaymentTransaction
from src.app.observability.logging import get_logger
from src.app.shared.errors import IdempotencyConflictError, OrderInvalidStateError, PaymentVerificationError

logger = get_logger("payments")


class PaymentService:
    """Service handling payments, Telegram Stars verification, idempotency and fulfillment triggering."""

    @staticmethod
    async def verify_pre_checkout(
        session: AsyncSession,
        order_id: uuid.UUID,
        total_amount: int,
        currency: str,
    ) -> bool:
        """Validates pre-checkout query: checks order status, currency, and exact amount."""
        stmt = select(Order).where(Order.id == order_id)
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            logger.warning(f"Pre-checkout failed: Order {order_id} not found.")
            return False

        if order.status != "pending_payment":
            logger.warning(f"Pre-checkout failed: Order {order_id} status is '{order.status}' (expected pending_payment).")
            return False

        if order.currency_code != currency:
            logger.warning(
                f"Pre-checkout currency mismatch for order {order_id}: expected {order.currency_code}, got {currency}"
            )
            return False

        if order.total_minor != total_amount:
            logger.warning(
                f"Pre-checkout amount mismatch for order {order_id}: expected {order.total_minor}, got {total_amount}"
            )
            return False

        return True

    @staticmethod
    async def process_successful_payment(
        session: AsyncSession,
        order_id: uuid.UUID,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str,
        total_amount: int,
        currency: str,
    ) -> PaymentTransaction:
        """Processes successful Telegram Stars payment idempotently and triggers fulfillment."""
        # 1. Check idempotency record
        idempotency_key = f"tg_pay:{telegram_payment_charge_id}"
        stmt_idem = select(IdempotencyRecord).where(
            IdempotencyRecord.scope == "telegram_payment",
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        result_idem = await session.execute(stmt_idem)
        existing_idem = result_idem.scalar_one_or_none()

        if existing_idem:
            logger.info(f"Duplicate payment update ignored via idempotency key: {idempotency_key}")
            # Fetch existing payment transaction
            stmt_tx = select(PaymentTransaction).where(
                PaymentTransaction.telegram_payment_charge_id == telegram_payment_charge_id
            )
            res_tx = await session.execute(stmt_tx)
            tx = res_tx.scalar_one_or_none()
            if tx:
                return tx
            raise IdempotencyConflictError("Duplicate payment transaction already recorded.")

        # 2. Lock order
        stmt_order = select(Order).where(Order.id == order_id).with_for_update()
        result_order = await session.execute(stmt_order)
        order = result_order.scalar_one_or_none()

        if not order:
            raise PaymentVerificationError(f"Order {order_id} not found for payment.")

        if order.status == "paid":
            logger.info(f"Order {order_id} is already marked as paid.")

        # 3. Create payment transaction record
        tx = PaymentTransaction(
            id=uuid.uuid4(),
            order_id=order.id,
            user_id=order.user_id,
            provider="telegram_stars",
            status="succeeded",
            currency_code=currency,
            amount_minor=total_amount,
            invoice_payload=f"inv_{order.id}_{uuid.uuid4().hex[:8]}",
            telegram_payment_charge_id=telegram_payment_charge_id,
            provider_payment_charge_id=provider_payment_charge_id,
            succeeded_at=datetime.now(timezone.utc),
        )
        session.add(tx)

        # 4. Update order status
        order.status = "paid"
        order.paid_at = datetime.now(timezone.utc)

        # 5. Record idempotency record (valid for 30 days)
        idem = IdempotencyRecord(
            id=uuid.uuid4(),
            scope="telegram_payment",
            idempotency_key=idempotency_key,
            actor_user_id=order.user_id,
            request_fingerprint=None,
            response_status=200,
            response_body={"order_id": str(order.id), "amount": total_amount, "currency": currency},
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        session.add(idem)
        await session.flush()


        # 6. Enqueue fulfillment outbox task
        await enqueue_outbox_event(
            session=session,
            event_type="order.paid",
            aggregate_type="order",
            aggregate_id=order.id,
            payload={
                "order_id": str(order.id),
                "user_id": str(order.user_id),
                "amount": total_amount,
                "currency": currency,
            },
        )

        logger.info(f"Payment {tx.id} succeeded for order {order.id}. Enqueued 'order.paid' outbox event.")
        return tx
