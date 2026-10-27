import html
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import (
    education_levels_keyboard,
    footer_keyboard,
    main_menu_keyboard,
    notifications_toggle_keyboard,
    profile_home_keyboard,
    timezone_selection_keyboard,
)
from src.app.bot.states.fsm import ProfileFSM
from src.app.modules.accounts.models import User
from src.app.modules.education.service import EducationService

router = Router(name="profile")

DEFAULT_NOTIFICATION_PREFS = {
    "orders": True, "subs": True, "sessions": True, "study": True,
    "daily_question": False, "opportunities": True, "marketing": False,
}


@router.message(Command("profile"))
@router.callback_query(F.data.in_(["home:profile", "menu:profile"]))
async def show_user_profile(event: Message | CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    await state.clear()
    stats = await EducationService.get_user_focus_stats(session, current_user.user_id)

    level_names = {
        1: "المرحلة الثانوية",
        2: "المرحلة الجامعية (السنوات الأولى)",
        3: "المرحلة الجامعية (المتقدمة)",
        4: "الدراسات العليا والماجستير",
        5: "خريج / باحث مستقل",
    }
    edu_level = "غير محدد"
    if current_user.learning_profile and current_user.learning_profile.education_level_id:
        edu_level = level_names.get(current_user.learning_profile.education_level_id, "طالب جامعي")

    profile_text = (
        "👤 <b>ملفك الشخصي والأكاديمي</b>\n\n"
        f"• الاسم: <b>{html.escape(current_user.display_name or 'صديقنا الطالب')}</b>\n"
        f"• المعرّف المرجعي: <code>{str(current_user.user_id)[:8].upper()}</code>\n"
        f"• المرحلة الدراسية: <b>{edu_level}</b>\n"
        f"• المنطقة الزمنية: <b>{current_user.time_zone}</b>\n"
        f"• اللغة: <b>العربية (ar)</b>\n"
        f"• حالة الحساب: <b>نشط</b>\n\n"
        "📈 <b>إحصائيات الإنجاز التعليمي:</b>\n"
        f"• جلسات التركيز المكتملة: <b>{stats['total_sessions']}</b> جلسة\n"
        f"• دقائق المذاكرة: <b>{stats['total_minutes']} دقيقة</b>\n\n"
        "اختر الإعداد الذي تود تعديله:"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(profile_text, reply_markup=profile_home_keyboard(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(profile_text, reply_markup=profile_home_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "prof:edu")
async def cb_profile_edit_edu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileFSM.wait_level)
    await callback.message.edit_text(
        "🎓 <b>تعديل المرحلة الدراسية:</b>\nاختر مرحلتك الحالية لتخصيص محتوى الكتالوج والاختبارات:",
        reply_markup=education_levels_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("onboard:level:"), ProfileFSM.wait_level)
async def cb_profile_save_level(callback: CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    val = callback.data.split(":")[2]
    if val.isdigit() and current_user.learning_profile:
        current_user.learning_profile.education_level_id = int(val)
        await session.commit()
    await state.clear()
    await callback.answer("تم تحديث المرحلة الدراسية بنجاح.")
    await show_user_profile(callback, current_user, session, state)


@router.callback_query(F.data == "prof:tz")
async def cb_profile_edit_tz(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileFSM.wait_tz)
    await callback.message.edit_text(
        "🌍 <b>تعديل المنطقة الزمنية:</b>\nاختر منطقتك الزمنية المعتمدة لجدولة جلسات التركيز والتذكيرات:",
        reply_markup=timezone_selection_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("onboard:tz:"), ProfileFSM.wait_tz)
async def cb_profile_save_tz(callback: CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    tz = callback.data.split(":")[2]
    if tz != "skip":
        current_user.time_zone = tz
        await session.commit()
    await state.clear()
    await callback.answer("تم حفظ المنطقة الزمنية.")
    await show_user_profile(callback, current_user, session, state)


@router.message(Command("notifications"))
@router.callback_query(F.data == "prof:notif")
async def show_notifications_settings(event: Message | CallbackQuery, current_user: User):
    prefs = dict(DEFAULT_NOTIFICATION_PREFS)
    if current_user.learning_profile:
        prefs.update(current_user.learning_profile.preferences.get("notifications", {}))

    text = (
        "🔔 <b>إعدادات الإشعارات والتنبيهات:</b>\n\n"
        "يمكنك تفعيل أو كتم التنبيهات غير الحرجة. الإشعارات التشغيلية للطلبات والاسترداد والأمان تبقى مفعلة دائماً لضمان وصول تحديثاتك الهامة.\n"
        "اضغط على أي بند لتغيير حالته:"
    )

    markup = notifications_toggle_keyboard(prefs)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("notif:toggle:"))
async def cb_toggle_notif(callback: CallbackQuery, current_user: User, session: AsyncSession):
    key = callback.data.split(":")[2]
    if key not in DEFAULT_NOTIFICATION_PREFS:
        await callback.answer("إعداد غير معروف.", show_alert=True)
        return
    prefs = dict(DEFAULT_NOTIFICATION_PREFS)
    if current_user.learning_profile:
        prefs.update(current_user.learning_profile.preferences.get("notifications", {}))

    prefs[key] = not prefs.get(key, True)
    if current_user.learning_profile:
        current_user.learning_profile.preferences = {
            **current_user.learning_profile.preferences,
            "notifications": prefs,
        }
        await session.commit()

    await callback.message.edit_reply_markup(reply_markup=notifications_toggle_keyboard(prefs))
    await callback.answer("تم تحديث الإعداد.")


@router.message(Command("language"))
async def cmd_language(message: Message):
    await message.answer(
        "🌐 <b>لغة الواجهة:</b>\n"
        "المنصة تعمل حالياً باللغة العربية بالكامل (Arabic - RTL). سيتم توفير واجهات بلغات إضافية في التحديثات القادمة.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
