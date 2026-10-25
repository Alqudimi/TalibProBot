import uuid
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import (
    categories_keyboard,
    main_menu_keyboard,
    service_card_keyboard,
    services_keyboard,
)
from src.app.bot.states.fsm import SearchStates
from src.app.modules.catalog.service import CatalogService

router = Router(name="catalog")


@router.callback_query(F.data == "menu:catalog")
async def cb_show_categories(callback: CallbackQuery, session: AsyncSession):
    categories = await CatalogService.get_active_categories(session)
    if not categories:
        await callback.message.edit_text(
            "📚 دليل الخدمات قيد التحديث حالياً. يرجى المحاولة لاحقاً.",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📚 <b>دليل الخدمات التعليمية والطلابية</b>\n\n"
        "اختر أحد التصنيفات لاستعراض الخدمات والمنتجات المتاحة:",
        reply_markup=categories_keyboard(categories),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def cb_show_category_services(callback: CallbackQuery, session: AsyncSession):
    cat_id_str = callback.data.split(":")[1]
    cat_id = uuid.UUID(cat_id_str)

    services = await CatalogService.get_services_by_category(session, cat_id, only_published=True)
    if not services:
        # Fallback to show any active services in this category
        services = await CatalogService.get_services_by_category(session, cat_id, only_published=False)

    if not services:
        await callback.answer("لا توجد خدمات متاحة في هذا التصنيف حالياً.", show_alert=True)
        return

    await callback.message.edit_text(
        f"📋 <b>الخدمات المتاحة ({len(services)} خدمة)</b>\n\n"
        "اضغط على الخدمة للاطلاع على تفاصيلها والتسعير والشروط:",
        reply_markup=services_keyboard(services, category_id=cat_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("srv:"))
async def cb_show_service_card(callback: CallbackQuery, session: AsyncSession):
    srv_id_str = callback.data.split(":")[1]
    srv_id = uuid.UUID(srv_id_str)

    details = await CatalogService.get_service_details(session, srv_id)
    if not details:
        await callback.answer("عذراً، لم يتم العثور على الخدمة المطلوبة.", show_alert=True)
        return

    service, offers = details

    text = f"✨ <b>{service.title_ar}</b>\n\n"
    if service.summary_ar:
        text += f"📝 <i>{service.summary_ar}</i>\n\n"

    delivery_mode_ar = {
        "automated_instant": "آلي فوري ⚡",
        "human_review": "مراجعة وإشراف بشري 👨‍🏫",
        "booking_session": "جلسة وحجز موعد 📅",
        "file_download": "تحميل رقمي فوري 📥",
        "configurable": "متعدد الخيارات ⚙️",
    }.get(service.default_delivery_mode, service.default_delivery_mode or "فوري")

    text += f"⚙️ <b>طريقة التنفيذ:</b> {delivery_mode_ar}\n\n"

    if service.integrity_policy_notes:
        text += f"🛡️ <b>تنبيه النزاهة:</b> {service.integrity_policy_notes}\n\n"

    if service.includes:
        text += f"✅ <b>يشمل:</b> {service.includes}\n"
    if service.excludes:
        text += f"❌ <b>لا يشمل:</b> {service.excludes}\n\n"

    # Pricing summary
    if offers:
        text += "💰 <b>خيارات الشراء والاشتراك:</b>\n"
        for o in offers:
            price_tag = "مجاني / تجريبي"
            if o.prices:
                p = o.prices[0]
                price_tag = f"{p.amount_minor / 100:.2f} {p.currency_code}"
            text += f"• {o.title_ar}: <b>{price_tag}</b>\n"

    await callback.message.edit_text(
        text,
        reply_markup=service_card_keyboard(service.id, offers),
        parse_mode="HTML",
    )
    await callback.answer()


# Search handlers
@router.callback_query(F.data == "menu:search")
async def cb_search_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchStates.waiting_for_query)
    await callback.message.edit_text(
        "🔍 <b>البحث في الخدمات التعليمية</b>\n\n"
        "أرسل الكلمة المفتاحية أو الموضوع الذي تبحث عنه (مثال: 'رياضيات'، 'اختبار'، 'خطة'، 'سيرة ذاتية'):",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SearchStates.waiting_for_query)
async def msg_search_execute(message: Message, state: FSMContext, session: AsyncSession):
    query_str = message.text.strip()
    await state.clear()

    results = await CatalogService.search_services(session, query_str)
    if not results:
        await message.answer(
            f"❌ لم يتم العثور على خدمات مطابقة لـ '<b>{query_str}</b>'. جرب كلمات بحث أخرى.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"🔍 <b>نتائج البحث عن '{query_str}' ({len(results)} خدمة):</b>",
        reply_markup=services_keyboard(results),
        parse_mode="HTML",
    )
