import html
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import (
    education_levels_keyboard,
    main_menu_keyboard,
    onboarding_consent_keyboard,
    support_home_keyboard,
    timezone_selection_keyboard,
)
from src.app.bot.keyboards.reply import persistent_reply_keyboard
from src.app.bot.states.fsm import OnboardingFSM
from src.app.bot.ui.templates import (
    MAIN_MENU_TEXT,
    SYSTEM_RESPONSES,
    WELCOME_NEW_USER,
)
from src.app.config.settings import settings
from src.app.modules.access_control.service import AccessControlService
from src.app.modules.accounts.models import ConsentDocument, User, UserConsent
from src.app.modules.accounts.service import AccountService

router = Router(name="start")

HELP_TEXT = """<b>دليل الاستخدام السريع للمنصة</b> 📚

1. <b>تصفح الخدمات:</b> اختر من بين 153 خدمة تعليمية مقسمة في 10 تصنيفات معتمدة عبر /services.
2. <b>متابعة الطلبات:</b> راجع سير تنفيذ طلباتك الحالية وتنزيل ملفاتك المكتملة عبر /orders.
3. <b>الاشتراكات والحقوق:</b> تحكم باشتراكاتك النشطة واستحقاقاتك المتبقية عبر /subscriptions.
4. <b>مركز المذاكرة:</b> نظّم جلسات تركيزك بالـ Pomodoro، وراجع البطاقات التكرارية، وأنشئ خططك عبر /edu.
5. <b>النزاهة الأكاديمية:</b> نساعدك على الفهم العميق واكتساب المهارة، ولا نقدّم حلولاً للامتحانات المباشرة.
6. <b>الدعم الفني:</b> يمكنك فتح تذكرة دعم أو تقديم بلاغ عن أي استفسار عبر /support."""

TERMS_TEXT = """<b>الشروط والأحكام والنزاهة الأكاديمية</b> 📜

<b>1. مبادئ النزاهة الأكاديمية:</b>
• كافة الخدمات مصممة لغرض الشرح، التوجيه، التلخيص، ومساعدتك على بناء المهارة والتعلم الذاتي.
• يُمنع منعاً باتاً طلب حل امتحانات جارية أو كتابة أبحاث كاملة نيابة عن الطالب أو اختلاق مراجع مزورة.

<b>2. سياسة الاسترداد:</b>
• المنتجات الرقمية الفورية: الاسترداد متاح إن لم تُستخدم أو تعذر تسليمها في المدة المحددة.
• الخدمات قيد التنفيذ: متاح مراجعة الطلب وتقديم طلب استرداد عبر الدعم الفني.
• بعد التسليم الكامل: لا استرداد للمبلغ، ويُعوّض الخلل بإعادة تنفيذ أو مراجعة مجانية.

<b>3. حقوق الخصوصية والبيانات:</b>
بياناتك تُجمع بالحد الأدنى اللازم لتشغيل الخدمة، ويمكنك طلب تصدير بياناتك أو حذف حسابك بأمر /privacy."""


async def _is_user_admin_or_provider(session: AsyncSession, user: User, tg_user_id: int) -> tuple[bool, bool]:
    is_admin = False
    admin_ids = settings.ADMIN_TELEGRAM_IDS
    if isinstance(admin_ids, list) and tg_user_id in admin_ids:
        is_admin = True
    else:
        perms = await AccessControlService.get_user_permissions(session, user.user_id)
        if "admin.super" in perms or "catalog.manage" in perms:
            is_admin = True

    is_provider = False
    perms = await AccessControlService.get_user_permissions(session, user.user_id)
    if "service.provide" in perms:
        is_provider = True

    return is_admin, is_provider


@router.message(CommandStart())
async def cmd_start(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    await state.clear()
    first_name = html.escape(message.from_user.first_name or "صديقنا الطالب")

    # Check if user has consented before
    stmt_consent = select(UserConsent).where(UserConsent.user_id == current_user.user_id)
    res = await session.execute(stmt_consent)
    existing_consent = res.scalars().first()

    if not existing_consent:
        # F1 Onboarding flow for new user
        text = WELCOME_NEW_USER.format(first_name=first_name)
        await message.answer(
            text,
            reply_markup=onboarding_consent_keyboard(),
            parse_mode="HTML",
        )
    else:
        # Returning user
        is_admin, is_provider = await _is_user_admin_or_provider(session, current_user, message.from_user.id)
        text = MAIN_MENU_TEXT.format(first_name=first_name)
        await message.answer(
            text,
            reply_markup=main_menu_keyboard(is_admin=is_admin, is_provider=is_provider),
            parse_mode="HTML",
        )

    # Attach persistent bottom reply keyboard
    await message.answer(
        "القائمة السريعة جاهزة دائماً في الأسفل 👇",
        reply_markup=persistent_reply_keyboard(),
    )


@router.callback_query(F.data == "onboard:agree")
async def cb_onboard_agree(callback: CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    # Grant terms and privacy consents
    stmt = select(ConsentDocument).where(ConsentDocument.retired_at.is_(None))
    docs = (await session.execute(stmt)).scalars().all()
    for doc in docs:
        consent = UserConsent(
            user_id=current_user.user_id,
            consent_document_id=doc.id,
            decision="granted",
        )
        session.add(consent)
    await session.commit()

    await state.set_state(OnboardingFSM.wait_level)
    await callback.message.edit_text(
        "خطوة 2 من 3:\n\n<b>ما مرحلتك الدراسية الحالية؟</b> (نحتاجها لتخصيص المحتوى المناسب لك)",
        reply_markup=education_levels_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("onboard:level:"))
async def cb_onboard_level(callback: CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    level_val = callback.data.split(":")[2]
    if level_val != "skip" and level_val.isdigit():
        if current_user.learning_profile:
            current_user.learning_profile.education_level_id = int(level_val)
            await session.commit()

    await state.set_state(OnboardingFSM.wait_tz)
    await callback.message.edit_text(
        "خطوة 3 من 3:\n\n<b>اختر منطقتك الزمنية</b> (لضبط مواعيد جلسات التركيز والتذكيرات بدقة):",
        reply_markup=timezone_selection_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("onboard:tz:"))
async def cb_onboard_tz(callback: CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    tz_val = callback.data.split(":")[2]
    if tz_val != "skip":
        current_user.time_zone = tz_val
        await session.commit()

    await state.clear()
    first_name = html.escape(callback.from_user.first_name or "")
    is_admin, is_provider = await _is_user_admin_or_provider(session, current_user, callback.from_user.id)

    completion_text = (
        "<b>جاهز! ✅ تم إعداد حسابك بنجاح.</b>\n\n"
        + MAIN_MENU_TEXT.format(first_name=first_name)
    )
    await callback.message.edit_text(
        completion_text,
        reply_markup=main_menu_keyboard(is_admin=is_admin, is_provider=is_provider),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(Command("menu"))
@router.message(F.text.in_(["🏠 الرئيسية", "القائمة"]))
async def cmd_menu(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    await state.clear()
    first_name = html.escape(message.from_user.first_name or "")
    is_admin, is_provider = await _is_user_admin_or_provider(session, current_user, message.from_user.id)
    await message.answer(
        MAIN_MENU_TEXT.format(first_name=first_name),
        reply_markup=main_menu_keyboard(is_admin=is_admin, is_provider=is_provider),
        parse_mode="HTML",
    )


@router.callback_query(F.data.in_(["home:menu", "nav:home"]))
async def cb_home_menu(callback: CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    await state.clear()
    first_name = html.escape(callback.from_user.first_name or "")
    is_admin, is_provider = await _is_user_admin_or_provider(session, current_user, callback.from_user.id)
    await callback.message.edit_text(
        MAIN_MENU_TEXT.format(first_name=first_name),
        reply_markup=main_menu_keyboard(is_admin=is_admin, is_provider=is_provider),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(Command("help"))
@router.message(F.text == "مساعدة")
async def cmd_help(message: Message):
    await message.answer(
        HELP_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("terms"))
@router.message(F.text == "الشروط")
@router.callback_query(F.data == "terms:read")
async def cmd_or_cb_terms(event: Message | CallbackQuery):
    if isinstance(event, CallbackQuery):
        await event.message.answer(TERMS_TEXT, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(TERMS_TEXT, parse_mode="HTML")


@router.message(Command("id"))
async def cmd_id(message: Message, current_user: User):
    short_ref = str(current_user.user_id)[:8].upper()
    await message.answer(
        f"المعرّف المرجعي لحسابك لدى الدعم: <code>{short_ref}</code>\n"
        "يمكنك تزويد فريق الدعم بهذا المعرّف عند الحاجة دون كشف أي بيانات شخصية.",
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
@router.message(F.text.in_(["✖️ إلغاء", "إلغاء"]))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer(
            "تم إلغاء العملية الجارية والعودة بأمان. لم يُفقد ما تم حفظه.",
            reply_markup=persistent_reply_keyboard(),
        )
    else:
        await message.answer(
            SYSTEM_RESPONSES["no_cancellable_flow"],
            reply_markup=persistent_reply_keyboard(),
        )
