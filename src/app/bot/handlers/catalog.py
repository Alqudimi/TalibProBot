import html
import uuid
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import (
    categories_keyboard,
    footer_keyboard,
    main_menu_keyboard,
    service_card_keyboard,
    services_list_keyboard,
)
from src.app.bot.states.fsm import SearchFSM
from src.app.bot.ui.templates import CATEGORY_EMOJIS, ERROR_MESSAGES, SERVICE_CARD_TEMPLATE
from src.app.modules.catalog.service import CatalogService

router = Router(name="catalog")


@router.message(Command("services"))
@router.message(F.text == "📚 الخدمات")
@router.callback_query(F.data.in_(["home:services", "menu:catalog", "cat:list"]))
async def show_catalog_categories(event: Message | CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    categories = await CatalogService.get_active_categories(session)

    text = (
        "📚 <b>كتالوج الخدمات التعليمية والأكاديمية</b>\n\n"
        "153 خدمة موثقة متكاملة — من الشرح الفوري والمساعدة في المذاكرة إلى مراجعة الأبحاث والتحضير للفرص.\n\n"
        "اختر أحد التصنيفات العشرة أدناه أو ابحث مباشرة عما تحتاجه:"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=categories_keyboard(categories), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=categories_keyboard(categories), parse_mode="HTML")


@router.callback_query(F.data == "cat:popular")
async def cb_popular_services(callback: CallbackQuery, session: AsyncSession):
    services = await CatalogService.get_popular_services(session, limit=10)
    if not services:
        services = await CatalogService.get_published_services(session, limit=10)

    text = "🔥 <b>الخدمات الأكثر طلباً واستخداماً:</b>\nاختر أي خدمة للاطلاع على تفاصيلها:"
    await callback.message.edit_text(
        text,
        reply_markup=services_list_keyboard(services, cat_code="popular", page=1, total_pages=1),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def cb_category_services(callback: CallbackQuery, session: AsyncSession):
    # Parse format cat:code or cat:code:pN
    parts = callback.data.split(":")
    if len(parts) < 2 or parts[1] in ["list", "search", "popular"]:
        return

    cat_code = parts[1]
    page = 1
    if len(parts) >= 3 and parts[2].startswith("p"):
        try:
            page = int(parts[2][1:])
        except ValueError:
            page = 1

    category = await CatalogService.get_category_by_code_or_id(session, cat_code)
    cat_id = category.id if category else None
    cat_title = category.name_ar if category else "الخدمات"
    cat_emoji = CATEGORY_EMOJIS.get(cat_code, "📁")

    services = []
    total_pages = 1
    if cat_id:
        services, total_pages = await CatalogService.get_services_paginated(
            session, category_id=cat_id, page=page, page_size=6, only_published=True
        )
        if not services:
            services, total_pages = await CatalogService.get_services_paginated(
                session, category_id=cat_id, page=page, page_size=6, only_published=False
            )

    if not services:
        await callback.answer("لا توجد خدمات متاحة في هذا التصنيف حالياً.", show_alert=True)
        return

    text = (
        f"{cat_emoji} <b>{cat_title}</b>\n"
        f"{category.description or ''}\n\n"
        f"تصفح الخدمات المتاحة — الصفحة {page}/{total_pages}:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=services_list_keyboard(services, cat_code=cat_code, page=page, total_pages=total_pages),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("svc:view:"))
async def cb_service_view(callback: CallbackQuery, session: AsyncSession):
    srv_id_str = callback.data.split(":")[2]
    try:
        srv_id = uuid.UUID(srv_id_str)
    except ValueError:
        await callback.answer(ERROR_MESSAGES["E-02"], show_alert=True)
        return

    details = await CatalogService.get_service_details(session, srv_id)
    if not details:
        await callback.answer(ERROR_MESSAGES["E-03"], show_alert=True)
        return

    service, offers = details
    cat_code = service.category.code if service.category else "instant_auto"
    cat_emoji = CATEGORY_EMOJIS.get(cat_code, "⚡")

    delivery_shape = {
        "automated_instant": "نتيجة نصية آلية خلال دقائق",
        "human_review": "مراجعة وإشراف متخصص (24-72 ساعة)",
        "booking_session": "جلسة فردية مباشرة 50 دقيقة",
        "file_download": "ملف تنزيل فوري",
        "configurable": "متعدد الخيارات بحسب الطلب",
    }.get(service.default_delivery_mode, "تنفيذ إلكتروني")

    sla_text = "خلال دقائق" if service.default_delivery_mode == "automated_instant" else "24-48 ساعة"

    price_display = "حسب العرض المختار"
    if offers and offers[0].prices:
        p = offers[0].prices[0]
        if p.currency_code == "XTR":
            price_display = f"{p.amount_minor} ⭐"
        else:
            price_display = f"{p.amount_minor / 100:.2f} {p.currency_code}"

    integrity_line = ""
    if service.integrity_policy_notes:
        integrity_line = f"\n⚠ <i>{service.integrity_policy_notes}</i>"

    text = SERVICE_CARD_TEMPLATE.format(
        service_title=html.escape(service.title_ar),
        category_emoji=cat_emoji,
        summary_ar=html.escape(service.summary_ar or ""),
        delivery_shape=delivery_shape,
        sla_text=sla_text,
        price_display=price_display,
        audience_hint="جميع المراحل الدراسية والجامعية",
        integrity_line=integrity_line,
    )

    await callback.message.edit_text(
        text,
        reply_markup=service_card_keyboard(service, offers, category_code=cat_code),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("svc:how:"))
async def cb_service_how(callback: CallbackQuery, session: AsyncSession):
    srv_id = uuid.UUID(callback.data.split(":")[2])
    details = await CatalogService.get_service_details(session, srv_id)
    if not details:
        await callback.answer()
        return
    service, _ = details

    text = (
        f"ℹ️ <b>كيف تعمل خدمة {service.title_ar}؟</b>\n\n"
        "1. اختيار العرض المناسب والاطلاع على تفاصيل التنفيذ.\n"
        "2. مراجعة وتأكيد الطلب ثم المتابعة لإتمام الدفع بـ Telegram Stars.\n"
        "3. إرسال المدخلات المطلوبة (نص أو ملف) بدقة بحسب الإرشادات.\n"
        "4. يبدأ النظام أو المراجع بتنفيذ طلبك وإشعارك فور اكتماله.\n"
        "5. استلام النتيجة مباشرة وحفظها في مكتبة ملفاتك مع خيار التقييم أو طلب المراجعة."
    )
    await callback.message.answer(text, reply_markup=footer_keyboard(f"svc:view:{srv_id}"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("svc:inputs:"))
async def cb_service_inputs(callback: CallbackQuery, session: AsyncSession):
    srv_id = uuid.UUID(callback.data.split(":")[2])
    details = await CatalogService.get_service_details(session, srv_id)
    if not details:
        await callback.answer()
        return
    service, _ = details

    input_reqs = "نص المشكلة أو السؤال الأكاديمي (حتى 2000 حرف)."
    if service.requires_upload:
        input_reqs += "\n• ملف داعم بصيغة PDF أو صورة واضحة (حجم أقصى 20MB)."

    text = (
        f"📝 <b>المدخلات المطلوبة لخدمة {service.title_ar}:</b>\n\n"
        f"• {input_reqs}\n\n"
        "💡 <i>تلميح: احرص على صياغة سؤالك بوضوح وتحديد الجزئية التي تحتاج فهماً أعمق لها للحصول على أفضل توجيه.</i>"
    )
    await callback.message.answer(text, reply_markup=footer_keyboard(f"svc:view:{srv_id}"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("svc:terms:"))
async def cb_service_terms(callback: CallbackQuery, session: AsyncSession):
    srv_id = uuid.UUID(callback.data.split(":")[2])
    text = (
        "📜 <b>الشروط وسياسة الاسترداد لهذه الخدمة:</b>\n\n"
        "• تُقدّم الخدمة لأغراض الإرشاد والتعليم والتدريب وتطوير المهارات.\n"
        "• يلتزم المستخدم بعدم استخدام المخرجات كبديل لجهده الذاتي في الامتحانات الرسمية.\n"
        "• الاسترداد متاح في حال تعذر إكمال الخدمة لأسباب تقنية من طرفنا.\n"
        "• يمكنك التواصل مع الدعم الفني عبر /support في أي مرحلة."
    )
    await callback.message.answer(text, reply_markup=footer_keyboard(f"svc:view:{srv_id}"), parse_mode="HTML")
    await callback.answer()


# Search Flow (§7.2.5)
@router.message(Command("search"))
@router.callback_query(F.data.in_(["cat:search", "menu:search"]))
async def cb_or_cmd_search(event: Message | CallbackQuery, state: FSMContext):
    await state.set_state(SearchFSM.wait_query)
    text = (
        "🔍 <b>البحث في كتالوج الخدمات</b>\n\n"
        "أرسل اسم المادة أو الموضوع أو المهارة التي تبحث عنها (على الأقل 3 أحرف):\n"
        "<i>أمثلة: رياضيات، برمجة، سيرة ذاتية، كيمياء، اختبار، آيلتس</i>"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=footer_keyboard("home:services"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=footer_keyboard("home:services"), parse_mode="HTML")


@router.message(SearchFSM.wait_query)
async def msg_search_perform(message: Message, state: FSMContext, session: AsyncSession):
    query = (message.text or "").strip()
    if len(query) < 3:
        await message.answer(
            ERROR_MESSAGES["E-01"].format(field="كلمة البحث", reason_short="قصيرة جداً", limit_text="3 أحرف على الأقل"),
            reply_markup=footer_keyboard("home:services"),
        )
        return

    await state.clear()
    results = await CatalogService.search_services(session, query)
    if not results:
        await message.answer(
            f"لا توجد نتائج مطابقة لـ \"{html.escape(query)}\". جرب كلمات أخرى أو تصفح التصنيفات.",
            reply_markup=footer_keyboard("home:services"),
        )
        return

    text = f"🔍 <b>نتائج البحث عن '{html.escape(query)}' ({len(results)} خدمة):</b>"
    await message.answer(
        text,
        reply_markup=services_list_keyboard(results, cat_code="search", page=1, total_pages=1),
        parse_mode="HTML",
    )
