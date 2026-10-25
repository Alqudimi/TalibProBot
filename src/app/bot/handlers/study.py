import uuid
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import focus_session_keyboard, main_menu_keyboard
from src.app.bot.states.fsm import FlashcardStates, FocusSessionStates
from src.app.modules.accounts.models import User
from src.app.modules.education.service import EducationService

router = Router(name="study")


# Focus Timer (Pomodoro)
@router.callback_query(F.data == "menu:focus")
async def cb_focus_menu(callback: CallbackQuery, current_user: User, session: AsyncSession):
    stats = await EducationService.get_user_focus_stats(session, current_user.user_id)

    fs = await EducationService.start_focus_session(
        session=session,
        user_id=current_user.user_id,
        subject_name="مذاكرة مركزة",
        planned_minutes=25,
    )

    text = (
        "⏱️ <b>بدأت جلسة التركيز الآن (25 دقيقة)!</b>\n\n"
        "ضع هاتفك في وضع التركيز وابدأ المذاكرة فوراً دون تشتت.\n"
        f"📊 إجمالي إنجازك السابق: <b>{stats['total_sessions']}</b> جلسات ({stats['total_minutes']} دقيقة).\n\n"
        "عند الانتهاء من المذاكرة، اضغط على الزر أدناه لتسجيل الإنجاز."
    )

    await callback.message.edit_text(
        text,
        reply_markup=focus_session_keyboard(fs.id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("focus_end:"))
async def cb_end_focus(callback: CallbackQuery, session: AsyncSession):
    fs_id_str = callback.data.split(":")[1]
    fs_id = uuid.UUID(fs_id_str)

    fs = await EducationService.complete_focus_session(session, fs_id)
    minutes = fs.actual_minutes if fs else 25

    await callback.message.edit_text(
        f"🎉 <b>رائع جداً! تم احتساب {minutes} دقيقة مذاكرة في سجلك!</b>\n\n"
        "خذ استراحة قصيرة لمدة 5 دقائق الآن لتجديد طاقتك.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# Flashcards
@router.callback_query(F.data == "menu:flashcards")
async def cb_flashcards_menu(callback: CallbackQuery, current_user: User, session: AsyncSession):
    decks = await EducationService.get_user_decks(session, current_user.user_id)
    text = "🃏 <b>مكتبة بطاقات الاستذكار (Flashcards)</b>\n\n"
    if not decks:
        # Create a sample default deck for the student
        deck = await EducationService.create_deck(
            session=session,
            user_id=current_user.user_id,
            title="مصطلحات ومفاهيم عامة",
            description="حزمة بطاقات تجريبية للمراجعة السريعة",
        )
        await EducationService.add_card(
            session=session,
            deck_id=deck.id,
            front="ما هو مبدأ الاسترجاع النشط (Active Recall)؟",
            back="اختبار نفسك واسترجاع المعلومة من الذاكرة بدلاً من القراءة السلبية المتكررة.",
        )
        await EducationService.add_card(
            session=session,
            deck_id=deck.id,
            front="ما هو التكرار المتباعد (Spaced Repetition)؟",
            back="مراجعة المعلومات على فترات زمنية متزايدة لترسيخها في الذاكرة طويلة المدى.",
        )
        decks = [deck]

    for d in decks:
        text += f"• <b>{d.title_ar}</b> ({d.card_count} بطاقة)\n"

    text += "\n💡 <i>البطاقات تساعدك على ترسيخ المعلومات ومراجعتها بسهولة قبل الاختبارات.</i>"

    await callback.message.edit_text(
        text,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
