import uuid
import pytest
from src.app.bot.keyboards.inline import (
    categories_keyboard,
    education_levels_keyboard,
    groups_keyboard,
    main_menu_keyboard,
    notifications_toggle_keyboard,
    onboarding_consent_keyboard,
    opportunities_keyboard,
    orders_tab_keyboard,
    privacy_home_keyboard,
    profile_home_keyboard,
    service_card_keyboard,
    services_list_keyboard,
    study_center_keyboard,
    support_home_keyboard,
    timezone_selection_keyboard,
)
from src.app.bot.keyboards.reply import cancel_reply_keyboard, persistent_reply_keyboard
from src.app.bot.states.fsm import (
    AdminBroadcastFSM,
    AdminCatalogFSM,
    AdminRefundFSM,
    AdminUserFSM,
    BookingFSM,
    GroupFSM,
    OnboardingFSM,
    PlanFSM,
    ProfileFSM,
    ReviewFSM,
    SearchFSM,
    ServiceInputFSM,
    TicketFSM,
    TimerFSM,
)
from src.app.bot.ui.templates import (
    ACADEMIC_INTEGRITY_MESSAGES,
    CATEGORY_EMOJIS,
    ERROR_MESSAGES,
    MAIN_MENU_TEXT,
    ORDER_REVIEW_TEMPLATE,
    PAYMENT_RECEIPT_TEMPLATE,
    WELCOME_NEW_USER,
)
from src.app.modules.catalog.models import ProductOffer, ServiceDefinition


def test_persistent_reply_keyboard_structure():
    kb = persistent_reply_keyboard()
    assert kb.is_persistent is True
    assert len(kb.keyboard) == 2
    row1 = [b.text for b in kb.keyboard[0]]
    row2 = [b.text for b in kb.keyboard[1]]
    assert "🏠 الرئيسية" in row1
    assert "📚 الخدمات" in row1
    assert "🗂️ طلباتي" in row2
    assert "🎧 الدعم" in row2
    assert "✖️ إلغاء" in row2


def test_cancel_reply_keyboard():
    kb = cancel_reply_keyboard()
    assert kb.keyboard[0][0].text == "✖️ إلغاء"


def test_main_menu_keyboard_variants():
    # Regular student
    kb_user = main_menu_keyboard(is_admin=False, is_provider=False)
    flat_texts = [btn.text for row in kb_user.inline_keyboard for btn in row]
    assert "📚 الخدمات" in flat_texts
    assert "🗂️ طلباتي" in flat_texts
    assert "🔁 اشتراكاتي" in flat_texts
    assert "📅 مواعيدي" in flat_texts
    assert "🧪 مركز المذاكرة" in flat_texts
    assert "🎯 الفرص" in flat_texts
    assert "🎧 الدعم" in flat_texts
    assert "👤 ملفي" in flat_texts
    assert "🛠️ لوحة الإدارة" not in flat_texts

    # Admin user
    kb_admin = main_menu_keyboard(is_admin=True, is_provider=False)
    flat_admin = [btn.text for row in kb_admin.inline_keyboard for btn in row]
    assert "🛠️ لوحة الإدارة" in flat_admin

    # Provider user
    kb_prov = main_menu_keyboard(is_admin=False, is_provider=True)
    flat_prov = [btn.text for row in kb_prov.inline_keyboard for btn in row]
    assert "🧑‍🏫 لوحة المزود" in flat_prov


def test_categories_keyboard_ten_official_categories():
    kb = categories_keyboard()
    flat_callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    expected_categories = [
        "cat:instant_auto",
        "cat:human_expert",
        "cat:subscriptions",
        "cat:digital_goods",
        "cat:institutional",
        "cat:ai_skills",
        "cat:employment",
        "cat:scholarships",
        "cat:tutoring",
        "cat:wellbeing",
    ]
    for cat in expected_categories:
        assert cat in flat_callbacks


def test_all_14_fsm_groups_defined():
    # Ensure all 14 groups have states
    groups = [
        OnboardingFSM,
        SearchFSM,
        ServiceInputFSM,
        BookingFSM,
        TicketFSM,
        ReviewFSM,
        ProfileFSM,
        PlanFSM,
        TimerFSM,
        GroupFSM,
        AdminCatalogFSM,
        AdminRefundFSM,
        AdminBroadcastFSM,
        AdminUserFSM,
    ]
    for g in groups:
        assert len(g.__states__) > 0


def test_error_matrix_completeness():
    # Verify E-01 through E-20
    for i in range(1, 21):
        code = f"E-{i:02d}"
        assert code in ERROR_MESSAGES
        msg = ERROR_MESSAGES[code]
        assert len(msg) > 5


def test_academic_integrity_matrix():
    # Verify AC-01 through AC-05
    for i in range(1, 6):
        code = f"AC-{i:02d}"
        assert code in ACADEMIC_INTEGRITY_MESSAGES
        msg = ACADEMIC_INTEGRITY_MESSAGES[code]
        assert len(msg) > 10


def test_financial_templates_have_no_emojis():
    # UI-UX §2.4 rule: no emojis in financial and sensitive confirmation templates
    forbidden_emojis = ["✅", "✨", "🎉", "🔥", "🛒", "📦", "🚀"]
    for emoji in forbidden_emojis:
        assert emoji not in ORDER_REVIEW_TEMPLATE
        assert emoji not in PAYMENT_RECEIPT_TEMPLATE


def test_all_secondary_hubs_keyboards():
    assert len(study_center_keyboard().inline_keyboard) >= 2
    assert len(support_home_keyboard().inline_keyboard) >= 2
    assert len(profile_home_keyboard().inline_keyboard) >= 2
    assert len(privacy_home_keyboard().inline_keyboard) >= 2
    assert len(opportunities_keyboard().inline_keyboard) >= 2
    assert len(groups_keyboard().inline_keyboard) >= 2
    assert len(orders_tab_keyboard().inline_keyboard) >= 1
    assert len(education_levels_keyboard().inline_keyboard) >= 2
    assert len(timezone_selection_keyboard().inline_keyboard) >= 2
