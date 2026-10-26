import html
import uuid
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import (
    focus_session_keyboard,
    footer_keyboard,
    main_menu_keyboard,
    study_center_keyboard,
)
from src.app.modules.accounts.models import User
from src.app.modules.education.models import Flashcard, FlashcardDeck, FocusSession, LearningPlan
from src.app.modules.education.service import EducationService

router = Router(name="study")


@router.message(Command("edu"))
@router.callback_query(F.data.in_(["home:edu", "edu:hub"]))
async def show_study_center(event: Message | CallbackQuery):
    text = (
        "🧪 <b>مركز المذاكرة والتعلم الذاتي</b>\n\n"
        "كل الأدوات الأكاديمية الذكية التي يحتاجها يومك الدراسي لتنظيم وقتك ومراجعة مقرراتك:\n\n"
        "• <b>الاختبارات وبنوك الأسئلة:</b> تدريب فوري وتصحيح ذاتي مع الشرح.\n"
        "• <b>بطاقات المذاكرة (Flashcards):</b> استذكار نشط وتكرار متباعد.\n"
        "• <b>خطة المذاكرة:</b> جدول يومي مخصص لمراجعة المقررات قبل الامتحانات.\n"
        "• <b>مؤقت التركيز (Pomodoro):</b> فترات مذاكرة منظمة بدون تشتت.\n"
        "• <b>السؤال اليومي:</b> تنشيط معرفتك بسؤال تفاعلي واحد كل يوم."
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=study_center_keyboard(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=study_center_keyboard(), parse_mode="HTML")


# 7.11.5 Focus Timer (/timer)
@router.message(Command("timer"))
@router.callback_query(F.data.in_(["edu:timer", "menu:focus"]))
async def cb_focus_timer_prompt(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    stats = await EducationService.get_user_focus_stats(session, current_user.user_id)

    fs = await EducationService.start_focus_session(
        session=session,
        user_id=current_user.user_id,
        subject_name="مذاكرة مركزة",
        planned_minutes=25,
    )

    text = (
        "⏱️ <b>بدأت جلسة التركيز الآن (25:00 دقيقة)!</b>\n\n"
        "• ضع هاتفك في وضع الصامت وابدأ مذاكرة هدفك المحدد.\n"
        f"• إجمالي إنجازك المسجل: <b>{stats['total_sessions']}</b> جلسة ({stats['total_minutes']} دقيقة).\n\n"
        "اضغط على الزر أدناه عند إتمام الجلسة لاحتساب الوقت في رصيدك:"
    )

    markup = focus_session_keyboard(fs.id)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("focus_end:"))
async def cb_end_focus_session(callback: CallbackQuery, session: AsyncSession):
    fs_id = uuid.UUID(callback.data.split(":")[1])
    fs = await EducationService.complete_focus_session(session, fs_id)
    minutes = fs.actual_minutes if fs else 25

    await callback.message.edit_text(
        f"🎉 <b>إنجاز ممتاز!</b> تم احتساب <b>{minutes}</b> دقيقة مذاكرة في سجلك الأكاديمي.\n\n"
        "خذ استراحة قصيرة لمدة 5 دقائق الآن لتجديد نشاطك وتركيزك.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# 7.11.2 Flashcards
@router.callback_query(F.data.in_(["edu:flashcards", "menu:flashcards"]))
async def cb_flashcards_hub(callback: CallbackQuery, current_user: User, session: AsyncSession):
    decks = await EducationService.get_user_decks(session, current_user.user_id)
    if not decks:
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
            back="اختبار النفس واستدعاء المعلومة من الذاكرة بدلاً من إعادة القراءة السلبية.",
        )
        await EducationService.add_card(
            session=session,
            deck_id=deck.id,
            front="ما هو التكرار المتباعد (Spaced Repetition)؟",
            back="مراجعة المعلومات على فترات متباعدة تدريجياً لترسيخها في الذاكرة طويلة المدى.",
        )
        decks = [deck]

    text = f"🃏 <b>مكتبة بطاقات الاستذكار (Flashcards) — {len(decks)} حزمة:</b>\n\n"
    builder = InlineKeyboardBuilder()
    for d in decks:
        title = getattr(d, "title_ar", getattr(d, "title", "حزمة بطاقات"))
        card_count = getattr(d, "card_count", 2)
        text += f"• <b>{title}</b> ({card_count} بطاقة)\n"
        builder.button(text=f"مراجعة: {title}", callback_data=f"edu:fc:rev:{d.id}")

    builder.button(text="🔙 رجوع لمركز المذاكرة", callback_data="home:edu")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("edu:fc:rev:"))
async def cb_flashcard_review(callback: CallbackQuery, session: AsyncSession):
    deck_id = uuid.UUID(callback.data.split(":")[3])
    stmt = select(Flashcard).where(Flashcard.deck_id == deck_id, Flashcard.is_active == True)
    cards = (await session.execute(stmt)).scalars().all()

    if not cards:
        await callback.answer("لا توجد بطاقات متاحة في هذه الحزمة حالياً.", show_alert=True)
        return

    card = cards[0]
    text = (
        f"🃏 <b>بطاقة مراجعة:</b>\n\n"
        f"❓ <b>السؤال:</b>\n{card.front_text}\n\n"
        "فكر في الإجابة أولاً، ثم اضغط على الزر أدناه لإظهار الشرح والتأكد:"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="👁️ أظهر الإجابة", callback_data=f"edu:fc:reveal:{card.id}")
    builder.button(text="🔙 رجوع", callback_data="edu:flashcards")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("edu:fc:reveal:"))
async def cb_flashcard_reveal(callback: CallbackQuery, session: AsyncSession):
    card_id = uuid.UUID(callback.data.split(":")[3])
    stmt = select(Flashcard).where(Flashcard.id == card_id)
    card = (await session.execute(stmt)).scalar_one_or_none()
    if not card:
        await callback.answer()
        return

    text = (
        f"🃏 <b>البطاقة:</b>\n\n"
        f"❓ <b>السؤال:</b>\n{card.front_text}\n\n"
        f"💡 <b>الإجابة النموذجية:</b>\n{card.back_text}\n\n"
        "كيف كان استذكارك للمعلومة؟"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ تذكرتها بسهولة", callback_data="edu:flashcards")
    builder.button(text="🔄 تحتاج مراجعة قريبة", callback_data="edu:flashcards")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🔙 قائمة البطاقات", callback_data="edu:flashcards"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


# 7.11.3 Study Plan (/plan)
@router.message(Command("plan"))
@router.callback_query(F.data == "edu:plan")
async def show_study_plan(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    stmt = (
        select(LearningPlan)
        .where(LearningPlan.user_id == current_user.user_id, LearningPlan.status == "active")
        .order_by(LearningPlan.created_at.desc())
    )
    res = await session.execute(stmt)
    plans = res.scalars().all()

    if not plans:
        text = (
            "🗓️ <b>خطتك الدراسية</b>\n\n"
            "لم تقم بإنشاء خطة مراجعة مجدولة بعد.\n"
            "يمكنك إنشاء خطة مذاكرة مخصصة تناسب تاريخ اختباراتك وساعات فراغك اليومية."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="✨ إنشاء خطة مذاكرة جديدة", callback_data="edu:plan:create")
        builder.button(text="🔙 رجوع", callback_data="home:edu")
        builder.adjust(1)
        markup = builder.as_markup()
    else:
        p = plans[0]
        text = (
            f"🗓️ <b>خطتك الدراسية الحالية: {html.escape(p.title)}</b>\n\n"
            f"• الهدف: {p.goal_description or 'مراجعة شاملة للمقررات'}\n"
            f"• الهدف اليومي: {p.daily_minutes_goal or 60} دقيقة\n"
            f"• تاريخ البدء: {p.starts_on.strftime('%Y-%m-%d') if p.starts_on else 'اليوم'}\n\n"
            "حافظ على معدل إنجازك اليومي لتحقيق أفضل استيعاب قبل الاختبارات!"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="⏱️ ابدأ جلسة مذاكرة الآن", callback_data="edu:timer")
        builder.button(text="🔙 رجوع", callback_data="home:edu")
        builder.adjust(1)
        markup = builder.as_markup()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "edu:plan:create")
async def cb_create_plan_sample(callback: CallbackQuery, current_user: User, session: AsyncSession):
    plan = LearningPlan(
        user_id=current_user.user_id,
        title="خطة المراجعة والاستعداد للاختبارات",
        goal_description="مراجعة المفاهيم الأساسية وحل الأسئلة التدريبية",
        daily_minutes_goal=60,
    )
    session.add(plan)
    await session.commit()

    await callback.message.edit_text(
        "✅ <b>تم إنشاء خطتك الدراسية بنجاح!</b>\n\n"
        "الهدف المقترح: <b>60 دقيقة</b> يومياً مقسمة إلى جلستي تركيز بنظام Pomodoro.\n"
        "تستطيع متابعة خطتك اليومية وجدولتك عبر أمر /plan.",
        reply_markup=footer_keyboard("home:edu"),
        parse_mode="HTML",
    )
    await callback.answer()


# 7.11.6 Daily Question (/daily)
@router.message(Command("daily"))
@router.callback_query(F.data == "edu:daily")
async def show_daily_question(event: Message | CallbackQuery):
    text = (
        "💡 <b>سؤال اليوم الأكاديمي</b>\n\n"
        "<b>السؤال في الكيمياء العامة:</b>\n"
        "ما هو نوع الرابطة الكيميائية الناتجة عن انتقال كامل للإلكترونات من ذرة إلى أخرى؟\n\n"
        "اختر الإجابة الصحيحة:"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="1. رابطة تساهمية", callback_data="edu:daily:ans:wrong")
    builder.button(text="2. رابطة أيونية", callback_data="edu:daily:ans:correct")
    builder.button(text="3. رابطة هيدروجينية", callback_data="edu:daily:ans:wrong")
    builder.button(text="4. رابطة فلزية", callback_data="edu:daily:ans:wrong")
    builder.adjust(2, 2)
    builder.row(InlineKeyboardButton(text="🔙 رجوع لمركز المذاكرة", callback_data="home:edu"))

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "edu:daily:ans:correct")
async def cb_daily_correct(callback: CallbackQuery):
    text = (
        "✅ <b>إجابة صحيحة وممتازة!</b>\n\n"
        "💡 <b>الشرح العلمي:</b>\n"
        "الرابطة الأيونية (Ionic Bond) تنشأ نتيجة انتقال إلكترون أو أكثر من ذرة فلزية لتكوين أيون موجب، إلى ذرة لا فلزية لتكوين أيون سالب، ويحدث التجاذب الكهروستاتيكي بينهما.\n\n"
        "🔥 <b>سلسلة إنجازك:</b> 1 يوم متتالٍ."
    )
    await callback.message.edit_text(text, reply_markup=footer_keyboard("home:edu"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "edu:daily:ans:wrong")
async def cb_daily_wrong(callback: CallbackQuery):
    text = (
        "❌ <b>إجابة غير صحيحة، حاول مجدداً!</b>\n\n"
        "تلميح: الرابطة المطلوبة تحدث بين ذرة تفقد إلكترونات وأخرى تكتسبها لتكوين أيونات موجبة وسالبة متعاكسة الشحنة."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 إعادة المحاولة", callback_data="edu:daily")
    builder.button(text="🔙 رجوع", callback_data="home:edu")
    builder.adjust(2)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


# 7.11.1 Quizzes
@router.callback_query(F.data == "edu:quizzes")
async def cb_quizzes_hub(callback: CallbackQuery):
    text = (
        "🧪 <b>بنك الاختبارات والتدريب الذاتي:</b>\n\n"
        "اختر أحد الاختبارات التدريبية المتاحة لتجربة مستواك مع تصحيح وشرح فوري:\n\n"
        "1. 📐 اختبار الرياضيات وحساب المثلثات\n"
        "2. ⚡ اختبار مفاهيم الفيزياء والحركة\n"
        "3. 💻 اختبار أساسيات البرمجة وهياكل البيانات"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="📐 بدء اختبار الرياضيات (5 أسئلة)", callback_data="edu:daily")
    builder.button(text="⚡ بدء اختبار الفيزياء (5 أسئلة)", callback_data="edu:daily")
    builder.button(text="🔙 رجوع لمركز المذاكرة", callback_data="home:edu")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()
