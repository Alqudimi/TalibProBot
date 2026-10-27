import html
import uuid
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import (
    footer_keyboard,
    main_menu_keyboard,
    order_review_keyboard,
    orders_tab_keyboard,
)
from src.app.bot.ui.templates import (
    DELIVERY_CARD_TEMPLATE,
    ERROR_MESSAGES,
    ORDER_REVIEW_TEMPLATE,
)
from src.app.modules.accounts.models import User
from src.app.modules.catalog.service import CatalogService
from src.app.modules.delivery.models import Delivery
from src.app.modules.orders.models import Order, OrderItem
from src.app.modules.orders.service import OrderService

router = Router(name="orders")


@router.callback_query(F.data.startswith("buy:") | F.data.startswith("svc:buy:"))
async def cb_create_order_review(callback: CallbackQuery, current_user: User, session: AsyncSession):
    parts = callback.data.split(":")
    offer_id_str = parts[-1]
    try:
        offer_id = uuid.UUID(offer_id_str)
    except ValueError:
        await callback.answer(ERROR_MESSAGES["E-02"], show_alert=True)
        return

    offer = await CatalogService.get_offer_by_id(session, offer_id)
    if not offer:
        await callback.answer(ERROR_MESSAGES["E-03"], show_alert=True)
        return

    # Create pending order
    order = await OrderService.create_order_from_offer(
        session=session,
        user_id=current_user.user_id,
        offer_id=offer.id,
        currency_code="XTR",
    )

    service_title = offer.primary_service.title_ar if offer.primary_service else offer.title_ar
    amount_display = f"{order.total_minor} ⭐" if order.currency_code == "XTR" else f"{order.total_minor / 100:.2f} {order.currency_code}"

    # Strict §6.3 Order Review (NO EMOJIS, formatted cleanly)
    review_text = ORDER_REVIEW_TEMPLATE.format(
        service_title=service_title,
        offer_title=offer.title_ar,
        amount=order.total_minor,
        currency_symbol_or_stars="⭐" if order.currency_code == "XTR" else order.currency_code,
        terms_summary="استخدام تعليمي وتدريبي شخصي وفق شروط المنصة وسياسة النزاهة الأكاديمية.",
        sla_text="24-48 ساعة",
    )

    await callback.message.edit_text(
        review_text,
        reply_markup=order_review_keyboard(order.id, payment_required=order.payment_required),
    )
    await callback.answer()


@router.message(Command("orders"))
@router.message(F.text == "🗂️ طلباتي")
@router.callback_query(F.data.in_(["home:my", "menu:orders", "ord:tab:active", "ord:tab:completed", "ord:tab:cancelled"]))
async def show_user_orders(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    tab = "active"
    if isinstance(event, CallbackQuery) and event.data.startswith("ord:tab:"):
        tab = event.data.split(":")[2]

    orders = await OrderService.get_user_orders(session, current_user.user_id, limit=10)

    # Filter by tab
    if tab == "active":
        filtered = [o for o in orders if o.status in ("pending_payment", "paid", "in_fulfillment")]
        tab_name = "الجارية"
    elif tab == "completed":
        filtered = [o for o in orders if o.status == "completed"]
        tab_name = "المكتملة"
    else:
        filtered = [o for o in orders if o.status in ("cancelled", "refunded")]
        tab_name = "الملغاة"

    status_ar_map = {
        "pending_payment": "⏳ بانتظار الدفع",
        "paid": "⚙️ قيد التجهيز",
        "in_fulfillment": "⚙️ قيد التنفيذ",
        "completed": "✅ مكتمل ومسلّم",
        "cancelled": "✖️ ملغى",
        "refunded": "↩️ مسترد",
    }

    if not filtered:
        text = f"🗂️ <b>طلباتك ({tab_name}):</b>\n\nلا توجد طلبات في هذا القسم حالياً."
    else:
        text = f"🗂️ <b>طلباتك ({tab_name}) — {len(filtered)} طلب:</b>\n\n"
        for o in filtered:
            ref = str(o.id)[:8].upper()
            status_text = status_ar_map.get(o.status, o.status)
            date_str = o.created_at.strftime("%Y-%m-%d %H:%M")
            service_name = o.items[0].product_title_snapshot if o.items else "خدمة تعليمية"
            text += f"• <b>طلب #{ref}</b> — {service_name}\n"
            text += f"  الحالة: {status_text} | المبلغ: {o.total_minor} {o.currency_code}\n"
            text += f"  التاريخ: {date_str}\n\n"

    markup = orders_tab_keyboard(current_tab=tab_name)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup, parse_mode="HTML")


@router.message(Command("downloads"))
@router.callback_query(F.data == "home:downloads")
async def show_user_downloads(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from src.app.modules.service_requests.models import ServiceRequest

    # Fetch available deliveries (from orders or service requests)
    stmt = (
        select(Delivery)
        .outerjoin(OrderItem, Delivery.order_item_id == OrderItem.id)
        .outerjoin(Order, OrderItem.order_id == Order.id)
        .outerjoin(ServiceRequest, Delivery.service_request_id == ServiceRequest.id)
        .where(
            ((Order.user_id == current_user.user_id) | (ServiceRequest.user_id == current_user.user_id)),
            Delivery.status.in_(["available", "delivered", "sent"]),
        )
        .order_by(Delivery.created_at.desc())
        .limit(10)
    )
    res = await session.execute(stmt)
    deliveries = res.scalars().all()

    builder = InlineKeyboardBuilder()

    if not deliveries:
        text = (
            "📥 <b>مكتبة ملفاتك وتنزيلاتك الرقمية:</b>\n\n"
            "لا توجد ملفات جاهزة للتنزيل حالياً. عند شراء أي منتج رقمي أو اكتمال تسليم طلباتك، ستظهر روابط التنزيل المباشرة هنا."
        )
        builder.button(text="📚 تصفح الخدمات", callback_data="home:services")
        builder.button(text="🏠 الرئيسية", callback_data="home:menu")
        builder.adjust(1)
    else:
        text = f"📥 <b>ملفاتك وتنزيلاتك المتاحة ({len(deliveries)} تسليم):</b>\n\n"
        for d in deliveries:
            d_ref = str(d.id)[:8].upper()
            date_str = d.created_at.strftime("%Y-%m-%d %H:%M")
            text += f"• 📄 <b>تسليم #{d_ref}</b> — متاح منذ {date_str}\n"
            builder.button(text=f"📖 عرض محتوى #{d_ref}", callback_data=f"deliv:view:{d.id}")

        builder.button(text="🏠 الرئيسية", callback_data="home:menu")
        builder.adjust(1)

    markup = builder.as_markup()
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("deliv:view:"))
async def cb_view_delivery_content(callback: CallbackQuery, current_user: User, session: AsyncSession):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from src.app.modules.files.models import StoredAsset
    from src.app.modules.service_requests.models import ServiceRequest

    deliv_id_str = callback.data.split(":")[2]
    try:
        deliv_id = uuid.UUID(deliv_id_str)
    except (ValueError, IndexError):
        await callback.answer(ERROR_MESSAGES["E-02"], show_alert=True)
        return

    stmt = (
        select(Delivery)
        .outerjoin(OrderItem, Delivery.order_item_id == OrderItem.id)
        .outerjoin(Order, OrderItem.order_id == Order.id)
        .outerjoin(ServiceRequest, Delivery.service_request_id == ServiceRequest.id)
        .where(
            Delivery.id == deliv_id,
            ((Order.user_id == current_user.user_id) | (ServiceRequest.user_id == current_user.user_id)),
        )
    )
    delivery = (await session.execute(stmt)).scalar_one_or_none()
    if not delivery:
        await callback.answer(ERROR_MESSAGES["E-03"], show_alert=True)
        return

    asset = await session.get(StoredAsset, delivery.asset_id)
    content_meta = asset.metadata_ if asset and asset.metadata_ else {}

    title = content_meta.get("title", "المحتوى الأكاديمي المسلّم")
    rendered = content_meta.get("rendered_output") or content_meta.get("summary") or "تم تسليم الطلب بنجاح."

    text_msg = (
        f"📄 <b>{html.escape(title)}</b> (#{str(delivery.id)[:8].upper()})\n\n"
        f"{rendered[:3500]}"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 العودة للتنزيلات", callback_data="home:downloads")
    builder.button(text="🏠 الرئيسية", callback_data="home:menu")
    builder.adjust(1)

    await callback.message.edit_text(text_msg, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("ord:cancel:") | F.data.startswith("cancel_order:"))
async def cb_cancel_order_unified(callback: CallbackQuery, current_user: User, session: AsyncSession):
    order_id_str = callback.data.split(":")[-1]
    try:
        order_id = uuid.UUID(order_id_str)
        await OrderService.cancel_order(session, order_id, current_user.user_id)
        await callback.message.edit_text(
            f"تم إلغاء الطلب #{str(order_id)[:8].upper()} بنجاح. لم يتم خصم أي مبالغ مالية.",
            reply_markup=main_menu_keyboard(),
        )
    except Exception as e:
        await callback.answer(f"تعذر إلغاء الطلب: {e}", show_alert=True)
    await callback.answer()
