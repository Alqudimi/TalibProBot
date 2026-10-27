import html
import uuid
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import (
    focus_session_keyboard,
    footer_keyboard,
    main_menu_keyboard,
    study_center_keyboard,
)
from src.app.bot.keyboards.reply import cancel_reply_keyboard, persistent_reply_keyboard
from src.app.bot.states.fsm import FlashcardFSM
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
    try:
        fs_id = uuid.UUID(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("معرّف جلسة التركيز غير صالح.", show_alert=True)
        return
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

    builder.button(text="➕ إنشاء حزمة جديدة", callback_data="edu:fc:create")
    builder.button(text="🔙 رجوع لمركز المذاكرة", callback_data="home:edu")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "edu:fc:create")
async def cb_flashcard_create_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FlashcardFSM.wait_deck_title)
    await callback.message.answer(
        "🃏 <b>إنشاء حزمة بطاقات جديدة:</b>\n\nأرسل الآن اسم أو عنوان الحزمة (مثلاً: مصطلحات الشبكات، أو قوانين الكيمياء):",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(FlashcardFSM.wait_deck_title)
async def handle_deck_title(message: Message, state: FSMContext, current_user: User, session: AsyncSession):
    if not message.text or message.text.strip() == "❌ إلغاء":
        await state.clear()
        await message.answer("تم إلغاء إنشاء الحزمة.", reply_markup=persistent_reply_keyboard())
        return

    title = message.text.strip()
    deck = await EducationService.create_deck(
        session=session,
        user_id=current_user.user_id,
        title=title,
        description=f"حزمة من إنشاء الطالب: {title}",
    )
    await state.update_data(deck_id=str(deck.id))
    await state.set_state(FlashcardFSM.wait_card_front)
    await message.answer(
        f"✅ تم إنشاء حزمة <b>{html.escape(title)}</b> بنجاح!\n\n"
        "الآن، أرسل <b>وجه البطاقة الأولى (السؤال أو المصطلح)</b>:",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="HTML",
    )


@router.message(FlashcardFSM.wait_card_front)
async def handle_card_front(message: Message, state: FSMContext):
    if not message.text or message.text.strip() == "❌ إلغاء":
        await state.clear()
        await message.answer("تم إلغاء الإضافة.", reply_markup=persistent_reply_keyboard())
        return

    front = message.text.strip()
    await state.update_data(front_text=front)
    await state.set_state(FlashcardFSM.wait_card_back)
    await message.answer(
        "ممتاز! أرسل الآن <b>ظهر البطاقة (الإجابة النموذجية أو التعريف)</b>:",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="HTML",
    )


@router.message(FlashcardFSM.wait_card_back)
async def handle_card_back(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text or message.text.strip() == "❌ إلغاء":
        await state.clear()
        await message.answer("تم إلغاء الإضافة.", reply_markup=persistent_reply_keyboard())
        return

    back = message.text.strip()
    data = await state.get_data()
    deck_id = uuid.UUID(data["deck_id"])
    front_text = data["front_text"]

    await EducationService.add_card(
        session=session,
        deck_id=deck_id,
        front=front_text,
        back=back,
    )
    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.button(text="🃏 مراجعة الحزمة الآن", callback_data=f"edu:fc:rev:{deck_id}")
    builder.button(text="🔙 قائمة البطاقات", callback_data="edu:flashcards")
    builder.adjust(1)

    await message.answer(
        "🎉 <b>تمت إضافة البطاقة بنجاح إلى حزمتك!</b>\n\n"
        "يمكنك الآن مراجعتها أو إضافة المزيد من البطاقات لاحقاً.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


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
async def cb_quizzes_hub(callback: CallbackQuery, session: AsyncSession):
    stmt = text("""
        SELECT q.id, q.title, q.description, count(qvi.id) as question_count
        FROM student_platform.quizzes q
        LEFT JOIN student_platform.quiz_versions qv ON qv.quiz_id = q.id
        LEFT JOIN student_platform.quiz_version_items qvi ON qvi.quiz_version_id = qv.id
        WHERE q.status = 'published'
        GROUP BY q.id, q.title, q.description
        ORDER BY q.title ASC
    """)
    res = await session.execute(stmt)
    quizzes = res.fetchall()

    if not quizzes:
        text_content = "🧪 <b>بنك الاختبارات والتدريب الذاتي:</b>\n\nلا توجد اختبارات منشورة حالياً."
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 رجوع لمركز المذاكرة", callback_data="home:edu")
        builder.adjust(1)
        await callback.message.edit_text(text_content, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
        return

    text_content = (
        "🧪 <b>بنك الاختبارات والتدريب الذاتي:</b>\n\n"
        "اختر أحد الاختبارات التدريبية المتاحة لتجربة مستواك مع تصحيح وشرح فوري:\n\n"
    )
    builder = InlineKeyboardBuilder()
    for q in quizzes:
        count = q.question_count or 0
        text_content += f"• <b>{html.escape(q.title)}</b> ({count} أسئلة)\n"
        builder.button(text=f"▶️ بدء {q.title}", callback_data=f"edu:quiz:take:{q.id}")

    builder.button(text="💡 سؤال اليوم السريع", callback_data="edu:daily")
    builder.button(text="🔙 رجوع لمركز المذاكرة", callback_data="home:edu")
    builder.adjust(1)
    await callback.message.edit_text(text_content, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("edu:quiz:take:"))
@router.callback_query(F.data.startswith("edu:quiz:q:"))
async def cb_quiz_question(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    quiz_id = uuid.UUID(parts[3])
    q_index = int(parts[4]) if len(parts) > 4 else 0

    stmt = text("""
        SELECT qv.id as qv_id, q.title as quiz_title, qver.id as qver_id, qver.prompt, qver.explanation, qvi.sort_order
        FROM student_platform.quizzes q
        JOIN student_platform.quiz_versions qv ON qv.quiz_id = q.id
        JOIN student_platform.quiz_version_items qvi ON qvi.quiz_version_id = qv.id
        JOIN student_platform.question_versions qver ON qver.id = qvi.question_version_id
        WHERE q.id = :quiz_id
        ORDER BY qvi.sort_order ASC
    """)
    rows = (await session.execute(stmt, {"quiz_id": quiz_id})).fetchall()
    if not rows or q_index >= len(rows):
        await callback.message.edit_text(
            "🎉 <b>أحسنت! أتممت جميع أسئلة هذا الاختبار التدريبي بنجاح!</b>\n\n"
            "استمر في المراجعة والتدريب لتثبيت المفاهيم العلمية.",
            reply_markup=footer_keyboard("edu:quizzes"),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    curr_q = rows[q_index]
    total_q = len(rows)

    opts_stmt = text("""
        SELECT id, option_text, is_correct, sort_order
        FROM student_platform.question_options
        WHERE question_version_id = :qver_id
        ORDER BY sort_order ASC
    """)
    options = (await session.execute(opts_stmt, {"qver_id": curr_q.qver_id})).fetchall()

    text_msg = (
        f"📝 <b>{html.escape(curr_q.quiz_title)}</b> (السؤال {q_index + 1} من {total_q})\n\n"
        f"<b>{html.escape(curr_q.prompt)}</b>\n\n"
        "اختر الإجابة الصحيحة:"
    )
    builder = InlineKeyboardBuilder()
    for opt in options:
        builder.button(text=opt.option_text, callback_data=f"edu:quiz:ans:{quiz_id}:{q_index}:{opt.id}")
    builder.adjust(1)
    builder.button(text="🔙 إنهاء الاختبار", callback_data="edu:quizzes")
    builder.adjust(1)

    await callback.message.edit_text(text_msg, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("edu:quiz:ans:"))
async def cb_quiz_answer(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    quiz_id = uuid.UUID(parts[3])
    q_index = int(parts[4])
    opt_id = uuid.UUID(parts[5])

    stmt = text("""
        SELECT opt.is_correct, opt.option_text, qver.explanation
        FROM student_platform.question_options opt
        JOIN student_platform.question_versions qver ON qver.id = opt.question_version_id
        WHERE opt.id = :opt_id
    """)
    row = (await session.execute(stmt, {"opt_id": opt_id})).fetchone()
    if not row:
        await callback.answer()
        return

    is_correct = row.is_correct
    explanation = row.explanation or "لا يوجد شرح إضافي."

    if is_correct:
        msg = f"✅ <b>إجابة صحيحة وممتازة!</b>\n\n💡 <b>الشرح:</b> {html.escape(explanation)}"
    else:
        msg = f"❌ <b>إجابة غير صحيحة!</b>\n\n💡 <b>التوضيح:</b> {html.escape(explanation)}"

    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ السؤال التالي", callback_data=f"edu:quiz:q:{quiz_id}:{q_index + 1}")
    builder.button(text="🔙 قائمة الاختبارات", callback_data="edu:quizzes")
    builder.adjust(1)

    await callback.message.edit_text(msg, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()
