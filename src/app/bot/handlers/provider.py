from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import footer_keyboard, main_menu_keyboard
from src.app.bot.ui.templates import ERROR_MESSAGES
from src.app.modules.access_control.service import AccessControlService
from src.app.modules.accounts.models import User

router = Router(name="provider")


async def _check_provider_permission(session: AsyncSession, user: User) -> bool:
    perms = await AccessControlService.get_user_permissions(session, user.user_id)
    return "service.provide" in perms or "admin.super" in perms


@router.message(Command("provider"))
@router.callback_query(F.data == "prov:home")
async def show_provider_dashboard(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    is_prov = await _check_provider_permission(session, current_user)
    if not is_prov:
        msg_text = "⛔ هذا القسم مخصص للمعلمين ومقدمي الخدمات المعتمدين في المنصة."
        if isinstance(event, CallbackQuery):
            await event.answer(msg_text, show_alert=True)
        else:
            await event.answer(msg_text)
        return

    text = (
        "🧑‍🏫 <b>لوحة تحكم مقدم الخدمة والمعلم</b>\n\n"
        "• الطلبات بانتظار المراجعة والقبول: <b>0</b> طلبات\n"
        "• جلسات التدريس المحجوزة لليوم: <b>0</b> جلسات\n"
        "• الأرباح المعلقة للتسوية: <b>0.00 XTR</b>\n"
        "• متوسط تقييم الطلاب: <b>5.0 / 5.0</b> ⭐\n\n"
        "الأوامر السريعة المتاحة:\n"
        "• /provider_requests — مراجعة وتأكيد الطلبات الموجهة لك\n"
        "• /provider_hours — ضبط فتحات التوافر الأسبوعية والإجازات"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=footer_keyboard("home:menu"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=footer_keyboard("home:menu"), parse_mode="HTML")


@router.message(Command("provider_requests"))
async def cmd_provider_requests(message: Message, current_user: User, session: AsyncSession):
    is_prov = await _check_provider_permission(session, current_user)
    if not is_prov:
        await message.answer(ERROR_MESSAGES["E-12"])
        return

    await message.answer(
        "📋 <b>الطلبات الموجهة لك للتنفيذ:</b>\n\n"
        "لا توجد طلبات جديدة بانتظار قبولك حالياً.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("provider_hours"))
async def cmd_provider_hours(message: Message, current_user: User, session: AsyncSession):
    is_prov = await _check_provider_permission(session, current_user)
    if not is_prov:
        await message.answer(ERROR_MESSAGES["E-12"])
        return

    await message.answer(
        "⏰ <b>إدارة ساعات التوافر والفتحات الزمنية:</b>\n\n"
        "• أيام العمل المعتمدة: الأحد إلى الخميس (16:00 - 21:00 بتوقيتك).\n"
        "• لإضافة إجازة أو تعديل ساعات التوافر، يمكنك مراسلة الإشراف الأكاديمي.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
