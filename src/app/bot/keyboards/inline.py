import uuid
from typing import Any, Dict, List, Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.app.bot.ui.templates import CATEGORY_EMOJIS
from src.app.modules.catalog.models import ProductOffer, ServiceCategory, ServiceDefinition


def main_menu_keyboard(is_admin: bool = False, is_provider: bool = False) -> InlineKeyboardMarkup:
    """Main Menu keyboard matching UI-UX.md §4.1."""
    builder = InlineKeyboardBuilder()
    # Row 1
    builder.button(text="📚 الخدمات", callback_data="home:services")
    builder.button(text="🗂️ طلباتي", callback_data="home:my")
    # Row 2
    builder.button(text="🔁 اشتراكاتي", callback_data="home:subs")
    builder.button(text="📅 مواعيدي", callback_data="home:bookings")
    # Row 3
    builder.button(text="🧪 مركز المذاكرة", callback_data="home:edu")
    builder.button(text="🎯 الفرص", callback_data="home:opp")
    # Row 4
    builder.button(text="🎧 الدعم", callback_data="home:support")
    builder.button(text="👤 ملفي", callback_data="home:profile")

    builder.adjust(2, 2, 2, 2)

    # Optional role-based bottom rows
    extra_buttons = []
    if is_provider:
        extra_buttons.append(InlineKeyboardButton(text="🧑‍🏫 لوحة المزود", callback_data="prov:home"))
    if is_admin:
        extra_buttons.append(InlineKeyboardButton(text="🛠️ لوحة الإدارة", callback_data="adm:home"))
    if extra_buttons:
        builder.row(*extra_buttons)

    return builder.as_markup()


def onboarding_consent_keyboard() -> InlineKeyboardMarkup:
    """Onboarding step 1: terms and consent."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 قراءة الشروط", callback_data="terms:read")
    builder.button(text="🛡️ الخصوصية", callback_data="priv:read")
    builder.button(text="✅ أوافق وأبدأ", callback_data="onboard:agree")
    builder.adjust(2, 1)
    return builder.as_markup()


def education_levels_keyboard() -> InlineKeyboardMarkup:
    """Onboarding step 2: education levels."""
    builder = InlineKeyboardBuilder()
    levels = [
        ("ثانوي", "1"),
        ("جامعي أولى", "2"),
        ("جامعي متقدم", "3"),
        ("دراسات عليا", "4"),
        ("خريج", "5"),
        ("تخطي الآن", "skip"),
    ]
    for label, val in levels:
        builder.button(text=label, callback_data=f"onboard:level:{val}")
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def timezone_selection_keyboard() -> InlineKeyboardMarkup:
    """Timezone selection options."""
    builder = InlineKeyboardBuilder()
    tzs = [
        ("مكة / الرياض (UTC+3)", "Asia/Riyadh"),
        ("القاهرة (UTC+2)", "Africa/Cairo"),
        ("دبي (UTC+4)", "Asia/Dubai"),
        ("بغداد (UTC+3)", "Asia/Baghdad"),
        ("توقيت غرينتش (UTC)", "UTC"),
        ("تخطي", "skip"),
    ]
    for label, tz in tzs:
        builder.button(text=label, callback_data=f"onboard:tz:{tz}")
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def categories_keyboard(
    categories: Optional[List[ServiceCategory]] = None,
) -> InlineKeyboardMarkup:
    """Full Catalog Categories Grid §4.2 & §7.2.1."""
    builder = InlineKeyboardBuilder()

    # 10 Official Categories with standardized emojis
    official_cats = [
        ("⚡ فورية آلية", "cat:instant_auto"),
        ("🧑‍🏫 بشرية وخبراء", "cat:human_expert"),
        ("🔁 اشتراكات", "cat:subscriptions"),
        ("📦 منتجات رقمية", "cat:digital_goods"),
        ("🏛️ مؤسسية", "cat:institutional"),
        ("🤖 AI وتقنية", "cat:ai_skills"),
        ("💼 توظيف", "cat:employment"),
        ("🎓 منح وقبول", "cat:scholarships"),
        ("👨‍🏫 دروس خصوصية", "cat:tutoring"),
        ("🧘 رفاه وإتاحة", "cat:wellbeing"),
    ]
    for label, cb in official_cats:
        builder.button(text=label, callback_data=cb)
    builder.adjust(2, 2, 2, 2, 2)

    # Search & Popular row
    builder.row(
        InlineKeyboardButton(text="🔍 بحث في الكتالوج", callback_data="cat:search"),
        InlineKeyboardButton(text="🔥 الأكثر طلباً", callback_data="cat:popular"),
    )
    # Footer row
    builder.row(
        InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"),
    )
    return builder.as_markup()


def services_list_keyboard(
    services: List[ServiceDefinition],
    cat_code: str,
    page: int = 1,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    """Paginated list of services inside a category (6 per page) §7.2.2."""
    builder = InlineKeyboardBuilder()
    for s in services:
        ref_id = str(s.id)[:8]
        builder.button(text=s.title_ar[:32], callback_data=f"svc:view:{s.id}")
    builder.adjust(1)

    # Pagination navigation
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ السابق", callback_data=f"cat:{cat_code}:p{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"[{page}/{total_pages}]", callback_data="sys:noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="التالي ▶️", callback_data=f"cat:{cat_code}:p{page + 1}"))
    if nav_buttons:
        builder.row(*nav_buttons)

    # Footer navigation
    builder.row(
        InlineKeyboardButton(text="📚 التصنيفات", callback_data="home:services"),
        InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"),
    )
    return builder.as_markup()


def service_card_keyboard(
    service: Any,
    offers: List[ProductOffer],
    category_code: str = "general",
) -> InlineKeyboardMarkup:
    """Service Card keyboard matching UI-UX.md §6.2."""
    builder = InlineKeyboardBuilder()
    svc_id = service.id if hasattr(service, "id") else service

    # Purchase button(s)
    for offer in offers:
        price_display = "طلب الآن"
        if offer.prices:
            p = offer.prices[0]
            if p.currency_code == "XTR":
                price_display = f"{p.amount_minor} ⭐"
            else:
                price_display = f"{p.amount_minor / 100:.2f} {p.currency_code}"
        builder.button(
            text=f"🛒 {offer.title_ar} — شراء ({price_display})",
            callback_data=f"svc:buy:{offer.id}",
        )

    # Detail tabs
    builder.button(text="كيف تعمل؟", callback_data=f"svc:how:{svc_id}")
    builder.button(text="المدخلات المطلوبة", callback_data=f"svc:inputs:{svc_id}")
    builder.button(text="الشروط والاسترداد", callback_data=f"svc:terms:{svc_id}")
    builder.adjust(1, 3)

    # Footer row
    builder.row(
        InlineKeyboardButton(text="🔙 التصنيف", callback_data=f"cat:{category_code}"),
        InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"),
    )
    return builder.as_markup()


def order_review_keyboard(order_id: uuid.UUID, payment_required: bool = True) -> InlineKeyboardMarkup:
    """Pre-payment review keyboard §6.3 (NO EMOJIS)."""
    builder = InlineKeyboardBuilder()
    if payment_required:
        builder.button(text="المتابعة إلى الدفع", callback_data=f"pay:go:{order_id}")
    else:
        builder.button(text="تأكيد وتفعيل الطلب", callback_data=f"pay:free:{order_id}")
    builder.button(text="إلغاء", callback_data=f"ord:cancel:{order_id}")
    builder.adjust(2)
    return builder.as_markup()


def orders_tab_keyboard(current_tab: str = "active") -> InlineKeyboardMarkup:
    """Tab selector for /orders §7.5.1."""
    builder = InlineKeyboardBuilder()
    tabs = [
        ("جارية", "ord:tab:active"),
        ("مكتملة", "ord:tab:completed"),
        ("ملغاة", "ord:tab:cancelled"),
        ("ملفاتي", "home:downloads"),
    ]
    for label, cb in tabs:
        marker = "• " if label == current_tab else ""
        builder.button(text=f"{marker}{label}", callback_data=cb)
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"))
    return builder.as_markup()


def study_center_keyboard() -> InlineKeyboardMarkup:
    """Study center options §7.11."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🧪 اختباراتي", callback_data="edu:quizzes")
    builder.button(text="🃏 بطاقات المراجعة", callback_data="edu:flashcards")
    builder.button(text="🗓️ خطتي الدراسية", callback_data="edu:plan")
    builder.button(text="⏱️ مؤقت التركيز", callback_data="edu:timer")
    builder.button(text="💡 السؤال اليومي", callback_data="edu:daily")
    builder.button(text="👥 مجموعات الدراسة", callback_data="edu:groups")
    builder.adjust(3, 3)
    builder.row(InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"))
    return builder.as_markup()


def support_home_keyboard() -> InlineKeyboardMarkup:
    """Support hub options §7.8.1."""
    builder = InlineKeyboardBuilder()
    builder.button(text="مشكلة في طلب", callback_data="sup:topic:order")
    builder.button(text="دفع أو استرداد", callback_data="sup:topic:finance")
    builder.button(text="سؤال عن خدمة", callback_data="sup:topic:service")
    builder.button(text="استفسار آخر", callback_data="sup:topic:other")
    builder.adjust(2, 2)
    builder.row(
        InlineKeyboardButton(text="📂 تذاكري", callback_data="sup:mine"),
        InlineKeyboardButton(text="❓ الأسئلة الشائعة", callback_data="sup:faq"),
    )
    builder.row(InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"))
    return builder.as_markup()


def profile_home_keyboard() -> InlineKeyboardMarkup:
    """User profile management keyboard §7.1.5."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎓 الملف التعليمي", callback_data="prof:edu")
    builder.button(text="🌍 المنطقة الزمنية", callback_data="prof:tz")
    builder.button(text="🔔 الإشعارات", callback_data="prof:notif")
    builder.button(text="📋 موافقاتي", callback_data="prof:consents")
    builder.adjust(2, 2)
    builder.row(
        InlineKeyboardButton(text="🛡️ الخصوصية وإدارة البيانات", callback_data="home:privacy"),
    )
    builder.row(InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"))
    return builder.as_markup()


def privacy_home_keyboard() -> InlineKeyboardMarkup:
    """Privacy center keyboard §7.10."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 طلب نسخة من بياناتي", callback_data="priv:export")
    builder.button(text="⚠️ حذف حسابي وبياناتي", callback_data="priv:delete_start")
    builder.button(text="📋 إدارة الموافقات", callback_data="priv:consents")
    builder.button(text="📜 سياسة الاحتفاظ بالبيانات", callback_data="priv:retention")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"))
    return builder.as_markup()


def notifications_toggle_keyboard(preferences: Dict[str, bool]) -> InlineKeyboardMarkup:
    """Notification kinds toggle keyboard §7.9."""
    builder = InlineKeyboardBuilder()
    kinds = [
        ("تحديثات الطلبات (إلزامي)", "orders", True),
        ("تحديثات الاشتراك (إلزامي)", "subs", True),
        ("تذكير الجلسات", "sessions", False),
        ("تذكيرات المذاكرة", "study", False),
        ("السؤال اليومي", "daily_question", False),
        ("تنبيهات الفرص", "opportunities", False),
        ("رسائل ترويجية (اختياري)", "marketing", False),
    ]
    for label, key, locked in kinds:
        is_on = preferences.get(key, True) if not locked else True
        icon = "✅" if is_on else "⚪"
        builder.button(
            text=f"{icon} {label}",
            callback_data=f"notif:toggle:{key}" if not locked else "sys:noop",
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"))
    return builder.as_markup()


def opportunities_keyboard() -> InlineKeyboardMarkup:
    """Opportunities and scholarships hub §7.12."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 بحث بالمطابقة", callback_data="opp:find")
    builder.button(text="📁 كل التصنيفات", callback_data="opp:categories")
    builder.button(text="⭐ الفرص المحفوظة", callback_data="opp:saved")
    builder.button(text="📅 تقويم المواعيد", callback_data="opp:calendar")
    builder.adjust(2, 2)
    builder.row(InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"))
    return builder.as_markup()


def groups_keyboard() -> InlineKeyboardMarkup:
    """Study groups hub §7.13."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 مجموعاتي", callback_data="grp:mine")
    builder.button(text="🔑 انضمام بكود", callback_data="grp:join")
    builder.button(text="➕ طلب إنشاء مجموعة", callback_data="grp:request")
    builder.adjust(2, 1)
    builder.row(InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"))
    return builder.as_markup()


def footer_keyboard(back_target: str = "home:services") -> InlineKeyboardMarkup:
    """Footer Bar §4.4."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 رجوع", callback_data=back_target)
    builder.button(text="🏠 الرئيسية", callback_data="home:menu")
    builder.adjust(2)
    return builder.as_markup()


def stale_button_keyboard() -> InlineKeyboardMarkup:
    """Graceful replacement for stale buttons §5.3."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 القائمة الرئيسية", callback_data="home:menu")
    return builder.as_markup()


def focus_session_keyboard(session_id: uuid.UUID) -> InlineKeyboardMarkup:
    """Focus timer session keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ إنهاء الجلسة واحتساب الوقت", callback_data=f"focus_end:{session_id}")
    builder.button(text="🏠 القائمة الرئيسية", callback_data="home:menu")
    builder.adjust(1)
    return builder.as_markup()

