from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import main_menu_keyboard
from src.app.modules.accounts.models import User
from src.app.modules.education.service import EducationService

router = Router(name="profile")


@router.callback_query(F.data == "menu:profile")
async def cb_user_profile(callback: CallbackQuery, current_user: User, session: AsyncSession):
    stats = await EducationService.get_user_focus_stats(session, current_user.user_id)

    profile_text = (
        "👤 <b>الملف الأكاديمي للطالب</b>\n\n"
        f"• الاسم الظاهر: <b>{current_user.display_name or 'طالب'}</b>\n"
        f"• المعرف الداخلي: <code>{str(current_user.user_id)[:8]}...</code>\n"
        f"• اللغة المفضلة: <b>{current_user.preferred_language.upper()}</b>\n"
        f"• المنطقة الزمنية: <b>{current_user.time_zone}</b>\n"
        f"• حالة الحساب: <b>{current_user.account_status}</b>\n\n"
        "📈 <b>إحصائيات الإنجاز:</b>\n"
        f"• عدد جلسات التركيز المكتملة: <b>{stats['total_sessions']}</b>\n"
        f"• دقائق المذاكرة المسجلة: <b>{stats['total_minutes']} دقيقة</b>\n"
        f"• تاريخ الانضمام: {current_user.created_at.strftime('%Y-%m-%d')}\n"
    )

    await callback.message.edit_text(
        profile_text,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
