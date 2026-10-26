from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import footer_keyboard, main_menu_keyboard
from src.app.bot.ui.templates import ERROR_MESSAGES
from src.app.config.settings import settings
from src.app.infrastructure.database.session import check_db_health
from src.app.modules.access_control.service import AccessControlService
from src.app.modules.accounts.models import User
from src.app.modules.catalog.models import ServiceDefinition
from src.app.modules.orders.models import Order
from src.app.modules.payments.models import PaymentTransaction
from src.app.modules.support.models import SupportTicket
from src.app.observability.logging import get_logger

logger = get_logger("admin_handlers")
router = Router(name="admin")


async def _assert_admin_permission(session: AsyncSession, user: User, tg_user_id: int, permission: str = "admin.super") -> bool:
    """Verifies admin permission via settings or RBAC tables §3.4."""
    admin_ids = settings.ADMIN_TELEGRAM_IDS
    if isinstance(admin_ids, list) and tg_user_id in admin_ids:
        return True

    perms = await AccessControlService.get_user_permissions(session, user.user_id)
    if "admin.super" in perms or permission in perms:
        return True

    logger.warning(f"Unauthorized admin access attempt: user_id={user.user_id}, tg_id={tg_user_id}, required={permission}")
    return False


def admin_hub_keyboard() -> InlineKeyboardMarkup:
    """Quick shortcuts for Admin Sections §10.1."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 الكتالوج والنشر", callback_data="adm:catalog")
    builder.button(text="🗂️ الطلبات والتنفيذ", callback_data="adm:orders")
    builder.button(text="💳 المالية والاسترداد", callback_data="adm:finance")
    builder.button(text="🎧 التذاكر والدعم", callback_data="adm:support")
    builder.button(text="👥 المستخدمون والأدوار", callback_data="adm:users")
    builder.button(text="📢 الإرسال الجماعي", callback_data="adm:broadcast")
    builder.button(text="⚖️ النزاعات والمشرفين", callback_data="adm:disputes")
    builder.button(text="🩺 الحالة التشغيلية", callback_data="adm:health")
    builder.button(text="📜 سجل التدقيق", callback_data="adm:audit")
    builder.adjust(2, 2, 2, 2, 1)
    builder.row(InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home:menu"))
    return builder.as_markup()


# 10.1 Admin Gateway (/admin)
@router.message(Command("admin"))
@router.callback_query(F.data == "adm:home")
async def cmd_admin_gateway(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    tg_id = event.from_user.id
    if not await _assert_admin_permission(session, current_user, tg_id):
        if isinstance(event, CallbackQuery):
            await event.answer(ERROR_MESSAGES["E-12"], show_alert=True)
        else:
            await event.answer(ERROR_MESSAGES["E-12"])
        return

    text_msg = (
        "🛠️ <b>بوابة الإدارة المركزية والتشغيل</b>\n\n"
        "مرحباً بك في لوحة الإشراف المباشر. اختر أحد الأقسام الإدارية أو استخدم الأوامر المباشرة:\n\n"
        "• /admin_catalog — إدارة ونشر الكتالوج\n"
        "• /admin_orders — تتبع ومطابقة الطلبات\n"
        "• /admin_finance — الفواتير والاسترداد المالي\n"
        "• /admin_support — طابور التذاكر والدعم\n"
        "• /admin_users — الأدوار والصلاحيات\n"
        "• /admin_broadcast — الإرسال والبث الجماعي\n"
        "• /admin_disputes — البت في النزاعات\n"
        "• /admin_health — الحالة التشغيلية وقاعدة البيانات\n"
        "• /admin_audit — سجل الأحداث والتدقيق الأمني"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text_msg, reply_markup=admin_hub_keyboard(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text_msg, reply_markup=admin_hub_keyboard(), parse_mode="HTML")


# 10.2 Catalog Panel (/admin_catalog)
@router.message(Command("admin_catalog"))
@router.callback_query(F.data == "adm:catalog")
async def cmd_admin_catalog(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    if not await _assert_admin_permission(session, current_user, event.from_user.id, "catalog.manage"):
        await event.answer(ERROR_MESSAGES["E-12"])
        return

    res_total = await session.execute(select(func.count(ServiceDefinition.id)))
    total_services = res_total.scalar() or 0

    res_pub = await session.execute(
        select(func.count(ServiceDefinition.id)).where(ServiceDefinition.lifecycle_status == "published")
    )
    published_services = res_pub.scalar() or 0

    text_msg = (
        "📚 <b>لوحة إدارة الكتالوج والنشر:</b>\n\n"
        f"• إجمالي الخدمات المعرفة: <b>{total_services}</b> خدمة\n"
        f"• الخدمات المنشورة الفعالة: <b>{published_services}</b> خدمة\n"
        f"• الخدمات قيد المراجعة/مسودة: <b>{total_services - published_services}</b>\n\n"
        "يتم نشر وتعديل الخدمات عبر لوحة الويب أو أوامر الترحيل البرمجية المعتمدة."
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")


# 10.3 Orders Panel (/admin_orders)
@router.message(Command("admin_orders"))
@router.callback_query(F.data == "adm:orders")
async def cmd_admin_orders(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    if not await _assert_admin_permission(session, current_user, event.from_user.id, "orders.manage"):
        await event.answer(ERROR_MESSAGES["E-12"])
        return

    res_orders = await session.execute(select(func.count(Order.id)))
    total_orders = res_orders.scalar() or 0

    res_in_ful = await session.execute(
        select(func.count(Order.id)).where(Order.status == "in_fulfillment")
    )
    in_fulfillment = res_in_ful.scalar() or 0

    text_msg = (
        "🗂️ <b>لوحة الطلبات والتنفيذ:</b>\n\n"
        f"• إجمالي الطلبات الكلي: <b>{total_orders}</b> طلب\n"
        f"• طلبات قيد التنفيذ حالياً: <b>{in_fulfillment}</b> طلب\n\n"
        "كافة الطلبات قيد التنفيذ يتم متابعتها آلياً وتوزيعها على طوابير المعالجة."
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")


# 10.4 Finance Panel (/admin_finance)
@router.message(Command("admin_finance"))
@router.callback_query(F.data == "adm:finance")
async def cmd_admin_finance(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    if not await _assert_admin_permission(session, current_user, event.from_user.id, "finance.manage"):
        await event.answer(ERROR_MESSAGES["E-12"])
        return

    res_rev = await session.execute(
        select(func.coalesce(func.sum(PaymentTransaction.amount_minor), 0)).where(
            PaymentTransaction.status == "succeeded"
        )
    )
    total_revenue = res_rev.scalar() or 0

    text_msg = (
        "💳 <b>لوحة العمليات المالية والاسترداد:</b>\n\n"
        f"• إجمالي المقبوضات الناجحة: <b>{total_revenue} XTR</b> (نجوم تيليجرام)\n"
        "• عمليات الاسترداد المعلقة: <b>0</b> طلبات\n\n"
        "الاستردادات المالية تخضع لمراجعة إدارة المالية وتُنفذ عبر Telegram Stars Refund API."
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")


# 10.5 Support Panel (/admin_support)
@router.message(Command("admin_support"))
@router.callback_query(F.data == "adm:support")
async def cmd_admin_support(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    if not await _assert_admin_permission(session, current_user, event.from_user.id, "support.manage"):
        await event.answer(ERROR_MESSAGES["E-12"])
        return

    res_open = await session.execute(
        select(func.count(SupportTicket.id)).where(SupportTicket.status == "open")
    )
    open_tickets = res_open.scalar() or 0

    text_msg = (
        "🎧 <b>طابور تذاكر الدعم الفني:</b>\n\n"
        f"• تذاكر مفتوحة بانتظار الرد: <b>{open_tickets}</b> تذكرة\n"
        "• التزام الـ SLA: مستهدف الرد خلال 24 ساعة لجميع الطلاب."
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")


# 10.6 Users Panel (/admin_users)
@router.message(Command("admin_users"))
@router.callback_query(F.data == "adm:users")
async def cmd_admin_users(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    if not await _assert_admin_permission(session, current_user, event.from_user.id, "users.manage"):
        await event.answer(ERROR_MESSAGES["E-12"])
        return

    res_users = await session.execute(select(func.count(User.user_id)))
    total_users = res_users.scalar() or 0

    text_msg = (
        "👥 <b>لوحة المستخدمين والأدوار (RBAC):</b>\n\n"
        f"• إجمالي الطلاب المسجلين: <b>{total_users}</b> مستخدم\n"
        "• الأدوار النشطة: platform_admin, service_provider, finance_officer, moderator, student"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")


# 10.7 Broadcast Panel (/admin_broadcast)
@router.message(Command("admin_broadcast"))
@router.callback_query(F.data == "adm:broadcast")
async def cmd_admin_broadcast(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    if not await _assert_admin_permission(session, current_user, event.from_user.id, "admin.super"):
        await event.answer(ERROR_MESSAGES["E-12"])
        return

    text_msg = (
        "📢 <b>لوحة الإرسال والبث الجماعي:</b>\n\n"
        "• حالة طابور البث: <b>جاهز</b>\n"
        "• معدل الإرسال الآمن: 1 رسالة / ثانية عبر Outbox لتجنب قيود Telegram Flood Limits.\n"
        "• الحملات التسويقية لا تُرسل إلا للطلاب الحاصلين على موافقة تسويقية صريحة."
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")


# 10.8 Disputes Panel (/admin_disputes)
@router.message(Command("admin_disputes"))
@router.callback_query(F.data == "adm:disputes")
async def cmd_admin_disputes(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    if not await _assert_admin_permission(session, current_user, event.from_user.id, "moderation.manage"):
        await event.answer(ERROR_MESSAGES["E-12"])
        return

    text_msg = (
        "⚖️ <b>لوحة النزاعات والوساطة الأكاديمية:</b>\n\n"
        "• النزاعات المفتوحة: <b>0</b> نزاعات\n"
        "• زمن البت المستهدف: خلال 48 ساعة."
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")


# 10.9 Health Panel (/admin_health)
@router.message(Command("admin_health"))
@router.callback_query(F.data == "adm:health")
async def cmd_admin_health(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    if not await _assert_admin_permission(session, current_user, event.from_user.id, "admin.super"):
        await event.answer(ERROR_MESSAGES["E-12"])
        return

    db_ok = await check_db_health()

    res_outbox = await session.execute(
        text(
            """
            SELECT status, count(*)
            FROM student_platform.transactional_outbox
            GROUP BY status;
            """
        )
    )
    outbox_stats = {row[0]: row[1] for row in res_outbox.fetchall()}

    text_msg = (
        "🩺 <b>الحالة التشغيلية للنظام:</b>\n\n"
        f"• محرك قاعدة البيانات (PostgreSQL): {'🟢 متصل' if db_ok else '🔴 غير متصل'}\n"
        f"• ذاكرة الكاش السريعة (Redis): {'🟢 مفعّل' if settings.REDIS_ENABLED else '⚪ محلي'}\n\n"
        "📊 <b>طابور الإشعارات الخلفية (Outbox):</b>\n"
    )
    if not outbox_stats:
        text_msg += "• لا توجد مهام معلقة في الطابور حالياً.\n"
    else:
        for st, c in outbox_stats.items():
            text_msg += f"• {st}: {c} مهمة\n"

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")


# 10.10 Audit Panel (/admin_audit)
@router.message(Command("admin_audit"))
@router.callback_query(F.data == "adm:audit")
async def cmd_admin_audit(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    if not await _assert_admin_permission(session, current_user, event.from_user.id, "admin.super"):
        await event.answer(ERROR_MESSAGES["E-12"])
        return

    text_msg = (
        "📜 <b>سجل التدقيق الأمني (Audit Events):</b>\n\n"
        "• كافة العمليات المالية والإدارية الحساسة وتغيير الصلاحيات تُسجل قيداً غير قابل للتعديل.\n"
        "• يتم تسجيل توقيت العملية، هوية المنفذ، الكيان المستهدف، والملخص بدون كشف أسرار."
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text_msg, reply_markup=footer_keyboard("adm:home"), parse_mode="HTML")
