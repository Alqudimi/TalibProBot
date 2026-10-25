import uuid
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import main_menu_keyboard, order_review_keyboard
from src.app.bot.states.fsm import ServiceOrderStates
from src.app.modules.accounts.models import User
from src.app.modules.orders.service import OrderService

router = Router(name="orders")


@router.callback_query(F.data.startswith("buy:"))
async def cb_create_order(callback: CallbackQuery, current_user: User, session: AsyncSession):
    offer_id_str = callback.data.split(":")[1]
    offer_id = uuid.UUID(offer_id_str)

    order = await OrderService.create_order_from_offer(
        session=session,
        user_id=current_user.user_id,
        offer_id=offer_id,
        currency_code="XTR",
    )

    review_text = (
        f"🧾 <b>ملخص الطلب #{str(order.id)[:8]}</b>\n\n"
        f"• المبلغ الإجمالي: <b>{order.total_minor} {order.currency_code}</b>\n"
        f"• حالة الدفع: <b>{order.status}</b>\n\n"
        "يرجى مراجعة الطلب والموافقة على المتابعة لإتمام العملية:"
    )

    await callback.message.edit_text(
        review_text,
        reply_markup=order_review_keyboard(order.id, order.payment_required),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_order:"))
async def cb_cancel_order(callback: CallbackQuery, current_user: User, session: AsyncSession):
    order_id_str = callback.data.split(":")[1]
    order_id = uuid.UUID(order_id_str)

    try:
        await OrderService.cancel_order(session, order_id, current_user.user_id)
        await callback.message.edit_text(
            f"❌ تم إلغاء الطلب #{str(order_id)[:8]} بنجاح.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.answer(f"تعذر إلغاء الطلب: {e}", show_alert=True)
    await callback.answer()


@router.callback_query(F.data == "menu:orders")
async def cb_list_user_orders(callback: CallbackQuery, current_user: User, session: AsyncSession):
    orders = await OrderService.get_user_orders(session, current_user.user_id, limit=8)
    if not orders:
        await callback.message.edit_text(
            "📦 <b>سجل الطلبات</b>\n\nليس لديك أي طلبات سابقة حتى الآن.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    text = "📦 <b>سجل طلباتك الأخيرة:</b>\n\n"
    for o in orders:
        status_icon = "🟢" if o.status in ("paid", "completed") else "🟡" if o.status == "pending_payment" else "⚪"
        text += (
            f"{status_icon} <b>طلب #{str(o.id)[:8]}</b>\n"
            f"   المبلغ: {o.total_minor} {o.currency_code} | الحالة: <i>{o.status}</i>\n"
            f"   التاريخ: {o.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
