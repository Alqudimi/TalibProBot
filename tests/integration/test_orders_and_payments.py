import uuid
import pytest
from sqlalchemy import select
from src.app.modules.accounts.service import AccountService
from src.app.modules.catalog.models import OfferPrice, ProductOffer, ServiceCategory, ServiceDefinition
from src.app.modules.orders.service import OrderService
from src.app.modules.payments.service import PaymentService


@pytest.mark.asyncio
async def test_order_creation_and_payment_flow(db_session):
    # 1. Setup user
    tg_id = 998877665
    user = await AccountService.get_or_create_telegram_user(
        db_session, telegram_id=tg_id, display_name="Test Student"
    )
    assert user.user_id is not None

    # 2. Setup category, service, offer and price
    cat = ServiceCategory(code=f"cat-{uuid.uuid4().hex[:6]}", name_ar="اختبارات وتدريب")
    db_session.add(cat)
    await db_session.flush()

    srv = ServiceDefinition(
        code=f"srv-{uuid.uuid4().hex[:6]}",
        category_id=cat.id,
        title_ar="شرح سؤال مع خطوات تفكيك الحل",
        summary_ar="شرح تفصيلي للمفاهيم والخطوات",
        lifecycle_status="published",
    )
    db_session.add(srv)
    await db_session.flush()

    offer = ProductOffer(
        code=f"off-{uuid.uuid4().hex[:6]}",
        primary_service_id=srv.id,
        title_ar="شرح سؤال واحد",
        offer_type="service",
        status="published",
    )
    db_session.add(offer)
    await db_session.flush()

    price = OfferPrice(offer_id=offer.id, currency_code="XTR", amount_minor=15)
    db_session.add(price)
    await db_session.flush()


    # 3. Create Order
    order = await OrderService.create_order_from_offer(
        session=db_session,
        user_id=user.user_id,
        offer_id=offer.id,
        currency_code="XTR",
    )
    assert order.status == "pending_payment"
    assert order.total_minor == 15
    assert order.currency_code == "XTR"

    # 4. Verify Pre-checkout
    valid_pre_checkout = await PaymentService.verify_pre_checkout(
        session=db_session,
        order_id=order.id,
        total_amount=15,
        currency="XTR",
    )
    assert valid_pre_checkout is True

    # 5. Process Successful Payment
    charge_id = f"tg_ch_{uuid.uuid4().hex[:12]}"
    tx = await PaymentService.process_successful_payment(
        session=db_session,
        order_id=order.id,
        telegram_payment_charge_id=charge_id,
        provider_payment_charge_id=f"prov_{charge_id}",
        total_amount=15,
        currency="XTR",
    )
    assert tx.status == "succeeded"
    assert order.status == "paid"

    # 6. Idempotency test: Re-submitting identical payment charge does not duplicate
    re_tx = await PaymentService.process_successful_payment(
        session=db_session,
        order_id=order.id,
        telegram_payment_charge_id=charge_id,
        provider_payment_charge_id=f"prov_{charge_id}",
        total_amount=15,
        currency="XTR",
    )
    assert re_tx.id == tx.id
