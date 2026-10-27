import html
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import footer_keyboard, groups_keyboard, main_menu_keyboard
from src.app.bot.keyboards.reply import cancel_reply_keyboard, persistent_reply_keyboard
from src.app.bot.states.fsm import GroupFSM
from src.app.modules.accounts.models import User

router = Router(name="groups")

GROUP_RULES_TEXT = """👥 <b>ميثاق وقواعد مجموعات الدراسة المضبوطة:</b>

1. <b>الاحترام والتعاون:</b> النقاش مخصص فقط للموضوعات الأكاديمية والمساعدة في المذاكرة.
2. <b>النزاهة الأكاديمية:</b> يُمنع منعاً باتاً نشر أو تبادل أسئلة أو حلول الاختبارات الرسمية الجارية.
3. <b>الأمان والخصوصية:</b> يُحظر نشر أي إعلانات أو روابط خارجية أو بيانات شخصية.
4. <b>الإشراف:</b> تخضع المجموعات لإشراف دوري، وأي مخالفة تؤدي إلى استبعاد فوري من المجموعة."""


@router.message(Command("groups"))
@router.message(F.text == "مجموعات")
@router.callback_query(F.data.in_(["home:groups", "edu:groups"]))
async def show_groups_hub(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "👥 <b>مجموعات الدراسة الأكاديمية</b>\n\n"
        "مجموعات صغيرة مضبوطة ومركزة (3-8 طلاب) تحت إشراف أكاديمي لتنظيم المراجعة ومناقشة المسائل المشتركة.\n\n"
        "اختر الإجراء المناسب:"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=groups_keyboard(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=groups_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "grp:mine")
async def cb_user_groups(callback: CallbackQuery, current_user: User, session: AsyncSession):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    rows = (await session.execute(text("""
        SELECT g.id, g.name, g.invite_code, m.member_role, m.joined_at,
               (SELECT count(*) FROM student_platform.study_group_members WHERE group_id = g.id AND status = 'active') AS member_count
        FROM student_platform.study_group_members m
        JOIN student_platform.study_groups g ON g.id = m.group_id
        WHERE m.user_id = :user_id AND m.status = 'active'
        ORDER BY m.joined_at DESC
    """), {"user_id": current_user.user_id})).mappings().all()

    builder = InlineKeyboardBuilder()

    if not rows:
        text_content = (
            "👥 <b>مجموعاتي الدراسية النشطة:</b>\n\n"
            "لا تنتمي حالياً إلى أي مجموعة دراسية نشطة.\n"
            "يمكنك الانضمام إلى مجموعة باستخدام رمز الدعوة الممنوح لك من المشرف، أو طلب الانضمام لنادي المذاكرة."
        )
        builder.button(text="🔑 الانضمام برمز دعوة", callback_data="grp:join")
        builder.button(text="🔙 رجوع", callback_data="home:groups")
        builder.adjust(1)
    else:
        text_content = f"👥 <b>مجموعاتك الدراسية النشطة ({len(rows)} مجموعة):</b>\n\n"
        for r in rows:
            text_content += (
                f"• <b>{html.escape(r['name'])}</b>\n"
                f"  دورك: {r['member_role']} | عدد الأعضاء: {r['member_count']}\n"
                f"  رمز الدعوة: <code>{r['invite_code']}</code>\n\n"
            )
        builder.button(text="🔑 الانضمام لمجموعة أخرى", callback_data="grp:join")
        builder.button(text="🔙 رجوع", callback_data="home:groups")
        builder.adjust(1)

    await callback.message.edit_text(text_content, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "grp:join")
async def cb_join_group_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GroupFSM.wait_code)
    await callback.message.answer(
        "🔑 <b>الانضمام إلى مجموعة دراسية:</b>\n\n"
        "أرسل رمز الانضمام المكوّن من 6 إلى 10 أحرف الممنوح لك من مشرف المجموعة:",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(GroupFSM.wait_code)
async def handle_group_code(message: Message, state: FSMContext, session: AsyncSession):
    code = (message.text or "").strip().upper()
    await state.clear()

    if len(code) < 4:
        await message.answer("الرمز غير صالح. يرجى التأكد من الرمز وإعادة المحاولة.", reply_markup=persistent_reply_keyboard())
        return
    exists = (await session.execute(text("""
        SELECT 1 FROM student_platform.study_groups
        WHERE invite_code = :code AND status = 'active'
    """), {"code": code})).scalar_one_or_none()
    if not exists:
        await message.answer("رمز الدعوة غير صالح أو انتهت صلاحيته.", reply_markup=persistent_reply_keyboard())
        return

    message_text = (
        f"✅ <b>تم التحقق من الرمز: {html.escape(code)}</b>\n\n"
        f"{GROUP_RULES_TEXT}\n\n"
        "هل توافق على الالتزام بالقواعد والانضمام للمجموعة؟"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ أوافق وانضم للمجموعة", callback_data=f"grp:confirm_join:{code}")
    builder.button(text="تراجع", callback_data="home:groups")
    builder.adjust(1)

    await message.answer(message_text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("grp:confirm_join:"))
async def cb_confirm_group_join(callback: CallbackQuery, current_user: User, session: AsyncSession):
    code = callback.data.split(":", 2)[2].strip().upper()
    group = (await session.execute(text("""
        SELECT id, name, capacity FROM student_platform.study_groups
        WHERE invite_code = :code AND status = 'active' FOR UPDATE
    """), {"code": code})).mappings().first()
    if not group:
        await callback.answer("رمز الدعوة غير صالح أو انتهت صلاحيته.", show_alert=True)
        return
    member_count = (await session.execute(text("""
        SELECT count(*) FROM student_platform.study_group_members
        WHERE group_id = :group_id AND status = 'active'
    """), {"group_id": group["id"]})).scalar() or 0
    if group["capacity"] is not None and member_count >= group["capacity"]:
        await callback.answer("المجموعة مكتملة العدد.", show_alert=True)
        return
    await session.execute(text("""
        INSERT INTO student_platform.study_group_members
            (group_id, user_id, member_role, status, rules_accepted_at)
        VALUES (:group_id, :user_id, 'member', 'active', now())
        ON CONFLICT (group_id, user_id) DO UPDATE
        SET status = 'active', rules_accepted_at = now()
    """), {"group_id": group["id"], "user_id": current_user.user_id})
    await session.commit()
    await callback.message.edit_text(
        f"🎉 <b>تم انضمامك إلى مجموعة {html.escape(group['name'])} بنجاح!</b>\n\n"
        "تم تسجيل موافقتك على القواعد وستصلك تحديثات المجموعة هنا.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "grp:request")
async def cb_request_new_group(callback: CallbackQuery):
    text = (
        "➕ <b>طلب إنشاء مجموعة دراسية جديدة:</b>\n\n"
        "إذا كنت تريد إنشاء مجموعة مخصصة لدفعتك أو مقرر دراسي محدد (3-8 أعضاء):\n"
        "يرجى فتح تذكرة عبر /support وسيقوم الفريق الأكاديمي بإعدادها وتزويدك برمز الانضمام."
    )
    await callback.message.edit_text(text, reply_markup=footer_keyboard("home:groups"), parse_mode="HTML")
    await callback.answer()
