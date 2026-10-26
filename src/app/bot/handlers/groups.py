import html
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
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
async def cb_user_groups(callback: CallbackQuery):
    text = (
        "👥 <b>مجموعاتي الدراسية النشطة:</b>\n\n"
        "لا تنتمي حالياً إلى أي مجموعة دراسية نشطة.\n"
        "يمكنك الانضمام إلى مجموعة باستخدام رمز الدعوة الممنوح لك من المشرف، أو طلب الانضمام لنادي المذاكرة."
    )
    await callback.message.edit_text(text, reply_markup=footer_keyboard("home:groups"), parse_mode="HTML")
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
async def handle_group_code(message: Message, state: FSMContext):
    code = (message.text or "").strip().upper()
    await state.clear()

    if len(code) < 4:
        await message.answer("الرمز غير صالح. يرجى التأكد من الرمز وإعادة المحاولة.", reply_markup=persistent_reply_keyboard())
        return

    text = (
        f"✅ <b>تم التحقق من الرمز: {html.escape(code)}</b>\n\n"
        f"{GROUP_RULES_TEXT}\n\n"
        "هل توافق على الالتزام بالقواعد والانضمام للمجموعة؟"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ أوافق وانضم للمجموعة", callback_data=f"grp:confirm_join:{code}")
    builder.button(text="تراجع", callback_data="home:groups")
    builder.adjust(1)

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("grp:confirm_join:"))
async def cb_confirm_group_join(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎉 <b>تم انضمامك إلى مجموعة الدراسة بنجاح!</b>\n\n"
        "تم إرسال إشعار لمشرف المجموعة، وستصلك التحديثات والملخصات اليومية هنا.",
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
