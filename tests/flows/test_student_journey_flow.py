import uuid
import pytest
from src.app.modules.accounts.models import ConsentDocument
from src.app.modules.accounts.service import AccountService
from src.app.modules.catalog.models import OfferPrice, ProductOffer, ServiceCategory, ServiceDefinition
from src.app.modules.delivery.service import DeliveryService
from src.app.modules.education.service import EducationService
from src.app.modules.entitlements.service import EntitlementService
from src.app.modules.files.service import FileStorageService
from sqlalchemy import select
from src.app.modules.orders.models import OrderItem
from src.app.modules.orders.service import OrderService
from src.app.modules.payments.service import PaymentService


@pytest.mark.asyncio
async def test_complete_student_academic_journey(db_session):
    """End-to-end user journey across accounts, catalog, orders, payments, entitlements, delivery, and study."""
    # 1. Onboarding & Registration
    tg_id = 77112233
    user = await AccountService.get_or_create_telegram_user(
        db_session, telegram_id=tg_id, display_name="Flow Student", username="flow_student"
    )
    assert user.user_id is not None

    # Consents
    terms_doc = (await db_session.execute(
        ConsentDocument.__table__.select().where(ConsentDocument.consent_type == "terms_of_service")
    )).first()
    if terms_doc:
        consent = await AccountService.record_consent(
            session=db_session,
            user_id=user.user_id,
            consent_document_id=terms_doc.id,
            action="agree",
        )
        assert consent.id is not None

    # Profile
    profile = await AccountService.upsert_learning_profile(
        db_session, user_id=user.user_id, university="جامعة الملك سعود", major="علوم الحاسب"
    )
    assert profile.major_or_track == "علوم الحاسب"

    # 2. Catalog & Offer Setup
    cat = ServiceCategory(code=f"cat-flow-{uuid.uuid4().hex[:6]}", name_ar="حقائب تعليمية متخصصة")
    db_session.add(cat)
    await db_session.flush()

    srv = ServiceDefinition(
        code=f"srv-flow-{uuid.uuid4().hex[:6]}",
        category_id=cat.id,
        title_ar="حقيبة المفاهيم الأساسية للخوارزميات",
        summary_ar="شرح مفصل مع خرائط مفاهيمية وبطاقات استذكار",
        lifecycle_status="published",
    )
    db_session.add(srv)
    await db_session.flush()

    offer = ProductOffer(
        code=f"off-flow-{uuid.uuid4().hex[:6]}",
        primary_service_id=srv.id,
        title_ar="الحقيبة الكاملة للخوارزميات",
        offer_type="service",
        status="published",
    )
    db_session.add(offer)
    await db_session.flush()

    price = OfferPrice(offer_id=offer.id, currency_code="XTR", amount_minor=25)
    db_session.add(price)
    await db_session.flush()

    # 3. Order Placement & Checkout
    order = await OrderService.create_order_from_offer(
        session=db_session,
        user_id=user.user_id,
        offer_id=offer.id,
        currency_code="XTR",
    )
    assert order.status == "pending_payment"
    assert order.total_minor == 25

    # 4. Telegram Stars Payment
    pre_checkout = await PaymentService.verify_pre_checkout(
        session=db_session, order_id=order.id, total_amount=25, currency="XTR"
    )
    assert pre_checkout is True

    charge_id = f"tg_ch_{uuid.uuid4().hex[:12]}"
    tx = await PaymentService.process_successful_payment(
        session=db_session,
        order_id=order.id,
        telegram_payment_charge_id=charge_id,
        provider_payment_charge_id=f"prov_{charge_id}",
        total_amount=25,
        currency="XTR",
    )
    assert tx.status == "succeeded"

    # Refresh order - trigger marks it paid!
    await db_session.refresh(order)
    assert order.status == "paid"

    # 5. Asset Registration & Delivery Fulfillment
    asset = await FileStorageService.register_asset(
        session=db_session,
        owner_user_id=user.user_id,
        storage_key=f"materials/algorithms_{uuid.uuid4().hex[:8]}.pdf",
        media_type="application/pdf",
        byte_size=1024 * 512,
        original_filename="Algorithms_CheatSheet.pdf",
    )
    assert asset.id is not None

    res_item = await db_session.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    order_item = res_item.scalars().first()
    assert order_item is not None

    delivery = await DeliveryService.create_delivery(
        session=db_session,
        asset_id=asset.id,
        order_item_id=order_item.id,
        idempotency_key=f"deliv:order:{order.id}:asset:{asset.id}",
    )
    assert delivery.status == "queued"

    attempt = await DeliveryService.record_delivery_attempt(
        session=db_session,
        delivery_id=delivery.id,
        channel="telegram",
        external_message_id="msg_12345",
        success=True,
    )
    assert attempt.status == "succeeded"
    assert delivery.status == "delivered"

    # 6. Self-Study: Flashcard Deck and Pomodoro Session
    deck = await EducationService.create_deck(
        session=db_session, user_id=user.user_id, title="خوارزميات البحث والترتيب"
    )
    assert deck.card_count == 0

    await EducationService.add_card(
        session=db_session,
        deck_id=deck.id,
        front="التعقيد الزمني لـ Binary Search",
        back="O(log n)",
    )
    assert deck.card_count == 1

    focus = await EducationService.start_focus_session(
        session=db_session, user_id=user.user_id, planned_minutes=45
    )
    assert focus.status == "running"
    completed_focus = await EducationService.complete_focus_session(db_session, focus.id)
    assert completed_focus.status == "completed"
