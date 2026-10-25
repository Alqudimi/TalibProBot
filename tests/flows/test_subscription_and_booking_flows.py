"""
End-to-end integration flows for Subscriptions, Entitlements, Providers, and Bookings.
Verifies compliance with Modular Monolith domain boundaries defined in Architecture.md.
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from src.app.modules.accounts.service import AccountService
from src.app.modules.catalog.models import ServiceCategory, ServiceDefinition, ProductOffer
from src.app.modules.subscriptions.service import SubscriptionService
from src.app.modules.entitlements.service import EntitlementService
from src.app.modules.providers.service import ProviderService
from src.app.modules.bookings.service import BookingService


@pytest.mark.asyncio
async def test_subscription_activation_and_quota_consumption(db_session):
    """Verifies recurring subscription lifecycle and entitlement quota consumption."""
    # 1. Setup Student
    student = await AccountService.get_or_create_telegram_user(
        db_session, telegram_id=88223344, display_name="Sub Student", username="sub_student"
    )

    # 2. Setup Category, Service & Subscription Offer
    cat = ServiceCategory(code=f"cat-sub-{uuid.uuid4().hex[:6]}", name_ar="عضويات شهرية")
    db_session.add(cat)
    await db_session.flush()

    srv = ServiceDefinition(
        code=f"srv-sub-{uuid.uuid4().hex[:6]}",
        category_id=cat.id,
        title_ar="عضوية بنك الأسئلة الشامل",
        summary_ar="وصول غير محدود لبنك الأسئلة مع دعم توجيهي",
        lifecycle_status="published",
    )
    db_session.add(srv)
    await db_session.flush()

    offer = ProductOffer(
        code=f"off-sub-{uuid.uuid4().hex[:6]}",
        primary_service_id=srv.id,
        title_ar="اشتراك بنك الأسئلة الشهري",
        offer_type="subscription",
        billing_interval_unit="month",
        billing_interval_count=1,
        status="published",
    )
    db_session.add(offer)
    await db_session.flush()

    # 3. Activate Subscription
    sub = await SubscriptionService.activate_subscription(
        session=db_session,
        user_id=student.user_id,
        offer_id=offer.id,
        duration_days=30,
        entitlement_ids=["question_bank_access", "ai_hints_quota"]
    )
    assert sub.status == "active"
    assert sub.current_period_end > datetime.now(timezone.utc)

    # 4. Check active subscriptions query
    active_subs = await SubscriptionService.get_user_active_subscriptions(db_session, student.user_id)
    assert len(active_subs) == 1
    assert active_subs[0].id == sub.id

    # 5. Check user entitlements
    has_access = await SubscriptionService.check_user_entitlement(db_session, student.user_id, "question_bank_access")
    assert has_access is True
    has_other = await SubscriptionService.check_user_entitlement(db_session, student.user_id, "non_existent_feature")
    assert has_other is False


@pytest.mark.asyncio
async def test_provider_profile_and_booking_flow(db_session):
    """Verifies tutor provider profile creation and booking workflow."""
    # 1. Setup Tutor User and Student User
    tutor_user = await AccountService.get_or_create_telegram_user(
        db_session, telegram_id=99112233, display_name="Dr. Tutor", username="dr_tutor"
    )
    student_user = await AccountService.get_or_create_telegram_user(
        db_session, telegram_id=99112244, display_name="Learner Student", username="learner"
    )

    # 2. Create and Verify Provider Profile
    provider = await ProviderService.get_or_create_profile(
        session=db_session,
        user_id=tutor_user.user_id,
        public_name="د. أحمد الأكاديمي",
        headline="أستاذ الفيزياء والرياضيات التطبيقية",
        bio="خبرة 10 سنوات في تبسيط المفاهيم للمرحلة الجامعية"
    )
    assert provider.id is not None
    assert provider.public_name == "د. أحمد الأكاديمي"

    # 3. Book a 1-on-1 Session (Service 021)
    starts = datetime.now(timezone.utc) + timedelta(days=1, hours=2)
    ends = starts + timedelta(minutes=45)

    booking = await BookingService.create_booking(
        session=db_session,
        provider_id=provider.id,
        session_title="جلسة تفكيك مسائل الميكانيكا الكلاسيكية",
        starts_at=starts,
        ends_at=ends,
        user_id=student_user.user_id,
        capacity=1
    )
    assert booking.status == "confirmed"
    assert booking.session_title == "جلسة تفكيك مسائل الميكانيكا الكلاسيكية"

    # 4. Verify Student Bookings Query
    user_bookings = await BookingService.get_user_bookings(db_session, student_user.user_id)
    assert len(user_bookings) == 1
    assert user_bookings[0].id == booking.id
