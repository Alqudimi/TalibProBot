import uuid
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import main_menu_keyboard
from src.app.bot.states.fsm import ServiceOrderStates
from src.app.modules.orders.service import OrderService
from src.app.modules.payments.service import PaymentService
from src.app.modules.service_requests.service import ServiceRequestService
from src.app.observability.logging import get_logger

logger = get_logger("payments_handler")
router = Router(name="payments")


@router.callback_query(F.data.startswith("pay:"))
async def cb_send_stars_invoice(callback: CallbackQuery, session: AsyncSession):
    order_id_str = callback.data.split(":")[1]
    order_id = uuid.UUID(order_id_str)

    order = await OrderService.get_order_by_id(session, order_id)
    if not order:
        await callback.answer("لم يتم العثور على الطلب.", show_alert=True)
        return

    if order.status != "pending_payment":
        await callback.answer(f"لا يمكن دفع الطلب بحالته الحالية: {order.status}", show_alert=True)
        return

    # Send Telegram Stars Invoice
    prices = [LabeledPrice(label="الخدمة الأكاديمية", amount=order.total_minor)]
    payload = f"order:{order.id}"

    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"دفع الطلب #{str(order.id)[:8]}",
        description="شراء الخدمة التعليمية عبر Telegram Stars بأمان وموثوقية فورية.",
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token="",  # Blank for Telegram Stars
    )
    await callback.answer()


@router.pre_checkout_query()
async def handle_pre_checkout_query(query: PreCheckoutQuery, session: AsyncSession):
    payload = query.invoice_payload
    if not payload.startswith("order:"):
        await query.answer(ok=False, error_message="طلب غير صالح.")
        return

    order_id_str = payload.split(":")[1]
    try:
        order_id = uuid.UUID(order_id_str)
        is_valid = await PaymentService.verify_pre_checkout(
            session=session,
            order_id=order_id,
            total_amount=query.total_amount,
            currency=query.currency,
        )
        if is_valid:
            await query.answer(ok=True)
        else:
            await query.answer(ok=False, error_message="بيانات الطلب غير متطابقة أو منتهية الصلاحية.")
    except Exception as e:
        logger.error(f"PreCheckout exception: {e}")
        await query.answer(ok=False, error_message="حدث خطأ أثناء معالجة الدفع، يرجى إعادة المحاولة.")


@router.message(F.successful_payment)
async def handle_successful_payment(message: Message, state: FSMContext, session: AsyncSession):
    sp = message.successful_payment
    payload = sp.invoice_payload
    order_id_str = payload.split(":")[1]
    order_id = uuid.UUID(order_id_str)

    tx = await PaymentService.process_successful_payment(
        session=session,
        order_id=order_id,
        telegram_payment_charge_id=sp.telegram_payment_charge_id,
        provider_payment_charge_id=sp.provider_payment_charge_id,
        total_amount=sp.total_amount,
        currency=sp.currency,
    )

    await state.set_state(ServiceOrderStates.waiting_for_prompt)
    await state.update_data(order_id=str(order_id))

    await message.answer(
        f"🎉 <b>تم تأكيد الدفع بنجاح!</b>\n\n"
        f"رقم المعاملة: <code>{tx.id}</code>\n"
        f"المبلغ المدفوع: <b>{sp.total_amount} {sp.currency}</b>\n\n"
        "✍️ <b>يرجى إرسال تفاصيل سؤالك أو المفهوم الذي تود شرحه أو خطة المذاكرة المطلوبة:</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("confirm_free:"))
async def cb_confirm_free_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    order_id_str = callback.data.split(":")[1]
    order_id = uuid.UUID(order_id_str)

    order = await OrderService.get_order_by_id(session, order_id)
    if not order:
        await callback.answer("لم يتم العثور على الطلب.", show_alert=True)
        return

    await state.set_state(ServiceOrderStates.waiting_for_prompt)
    await state.update_data(order_id=str(order_id))

    await callback.message.edit_text(
        "✅ <b>تم اعتماد الطلب المجاني بنجاح!</b>\n\n"
        "✍️ أرسل الآن سؤالك أو تفاصيل المفهوم الذي تريد شرحه وتفكيك خطواته:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ServiceOrderStates.waiting_for_prompt)
async def handle_service_prompt_input(message: Message, state: FSMContext, session: AsyncSession):
    prompt_text = message.text.strip()
    data = await state.get_data()
    order_id = uuid.UUID(data["order_id"])
    await state.clear()

    order = await OrderService.get_order_by_id(session, order_id)
    if not order or not order.items:
        await message.answer("حدث خطأ في استرجاع بيانات الطلب.", reply_markup=main_menu_keyboard())
        return

    service_id = order.items[0].service_id

    try:
        req = await ServiceRequestService.submit_request(
            session=session,
            order=order,
            service_id=service_id,
            prompt_text=prompt_text,
            title=f"طلب خدمة: {prompt_text[:30]}...",
        )
        await message.answer(
            f"🚀 <b>تم استلام طلبك وجارٍ معالجته!</b>\n\n"
            f"معرّف الطلب: <code>{req.id}</code>\n\n"
            "سيرسل لك البوت المخرجات التعليمية والخطوات التفصيلية فور اكتمالها.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(
            f"⚠️ {e}",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
