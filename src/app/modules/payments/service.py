import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.infrastructure.queue.outbox import enqueue_outbox_event
from src.app.modules.orders.models import Order
from src.app.modules.accounts.models import ExternalIdentity
from src.app.modules.payments.models import IdempotencyRecord, PaymentTransaction, Refund
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
        invoice_payload: str | None = None,
        payer_user_id: uuid.UUID | None = None,
    ) -> PaymentTransaction:
        """Processes successful Telegram Stars payment idempotently and triggers fulfillment."""
        # Lock the order before reading idempotency so concurrent updates for
        # the same order cannot both settle it.
        idempotency_key = f"tg_pay:{telegram_payment_charge_id}"
        stmt_order = select(Order).where(Order.id == order_id).with_for_update()
        result_order = await session.execute(stmt_order)
        order = result_order.scalar_one_or_none()

        if not order:
            raise PaymentVerificationError(f"Order {order_id} not found for payment.")
        if payer_user_id is not None and order.user_id != payer_user_id:
            raise PaymentVerificationError("Telegram payer does not own this order.")

        stmt_idem = select(IdempotencyRecord).where(
            IdempotencyRecord.scope == "telegram_payment",
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        existing_idem = (await session.execute(stmt_idem)).scalar_one_or_none()
        if existing_idem:
            stmt_tx = select(PaymentTransaction).where(
                PaymentTransaction.telegram_payment_charge_id == telegram_payment_charge_id
            )
            tx = (await session.execute(stmt_tx)).scalar_one_or_none()
            if tx:
                return tx
            raise IdempotencyConflictError("Duplicate payment transaction already recorded.")

        if order.status != "pending_payment":
            raise PaymentVerificationError(
                f"Order {order_id} is not payable in status '{order.status}'."
            )
        if order.currency_code != currency or order.total_minor != total_amount:
            raise PaymentVerificationError("Payment amount or currency does not match the order.")

        # 3. Create payment transaction record
        tx = PaymentTransaction(
            id=uuid.uuid4(),
            order_id=order.id,
            user_id=order.user_id,
            provider="telegram_stars",
            status="succeeded",
            currency_code=currency,
            amount_minor=total_amount,
            invoice_payload=invoice_payload or f"order:{order.id}",
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

    @staticmethod
    async def refund_stars_payment(
        session: AsyncSession,
        bot: Bot,
        payment_id: uuid.UUID,
        requested_by: uuid.UUID,
        reason_code: str = "admin_approved",
    ) -> Refund:
        """Refund a Telegram Stars payment exactly once.

        The local refund row is locked before calling Telegram. A completed
        refund is returned idempotently; an in-flight refund is rejected so a
        second admin cannot issue a duplicate provider call.
        """
        payment = (
            await session.execute(
                select(PaymentTransaction)
                .where(PaymentTransaction.id == payment_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not payment or payment.status != "succeeded":
            raise PaymentVerificationError("Payment is missing or is not refundable.")
        existing = (
            await session.execute(
                select(Refund)
                .where(Refund.payment_id == payment.id)
                .order_by(Refund.requested_at.desc())
                .with_for_update()
            )
        ).scalars().first()
        if existing and existing.status == "succeeded":
            return existing
        if existing and existing.status in {"processing", "requested"}:
            raise IdempotencyConflictError("A refund for this payment is already in progress.")
        if existing and existing.status in {"failed", "rejected", "cancelled"}:
            refund = existing
            refund.status = "processing"
            refund.failure_message_safe = None
        else:
            refund = Refund(
                id=uuid.uuid4(),
                payment_id=payment.id,
                order_id=payment.order_id,
                requested_by=requested_by,
                status="processing",
                currency_code=payment.currency_code,
                amount_minor=payment.amount_minor,
                reason_code=reason_code[:100],
            )
            session.add(refund)
        await session.flush()
        identity = (
            await session.execute(
                select(ExternalIdentity.telegram_user_id).where(
                    ExternalIdentity.user_id == payment.user_id,
                    ExternalIdentity.provider == "telegram",
                    ExternalIdentity.telegram_user_id.is_not(None),
                )
            )
        ).scalar_one_or_none()
        if not identity or not payment.telegram_payment_charge_id:
            refund.status = "failed"
            refund.failure_message_safe = "Telegram payer identity or charge id is missing."
            await session.commit()
            raise PaymentVerificationError(refund.failure_message_safe)
        try:
            await bot.refund_star_payment(
                user_id=identity,
                telegram_payment_charge_id=payment.telegram_payment_charge_id,
            )
        except Exception as exc:
            refund.status = "failed"
            refund.failure_message_safe = "Telegram refund provider call failed."
            await session.commit()
            logger.error("Telegram Stars refund failed", exc_info=exc)
            raise PaymentVerificationError("Telegram refund provider call failed.") from exc
        refund.status = "succeeded"
        refund.external_refund_id = f"tg_refund:{payment.telegram_payment_charge_id}"
        refund.completed_at = datetime.now(timezone.utc)
        order = (
            await session.execute(select(Order).where(Order.id == payment.order_id).with_for_update())
        ).scalar_one()
        # Follow the database state machine: paid -> refund_pending -> refunded.
        order.status = "refund_pending"
        await session.flush()
        order.status = "refunded"
        await session.commit()
        return refund
