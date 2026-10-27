import html
import uuid
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import footer_keyboard, main_menu_keyboard
from src.app.bot.keyboards.reply import cancel_reply_keyboard, persistent_reply_keyboard
from src.app.bot.states.fsm import ServiceInputFSM, ServiceOrderStates
from src.app.bot.ui.templates import (
    ACADEMIC_INTEGRITY_MESSAGES,
    ACKNOWLEDGEMENT_CARD_TEMPLATE,
    DELIVERY_CARD_TEMPLATE,
    ERROR_MESSAGES,
    PAYMENT_RECEIPT_TEMPLATE,
)
from src.app.modules.academic_services.engine import AcademicServiceEngine
from src.app.modules.academic_services.schemas import ServiceInput
from src.app.modules.accounts.models import User
from src.app.modules.orders.service import OrderService
from src.app.modules.payments.service import PaymentService
from src.app.modules.service_requests.service import AcademicIntegrityFilter, ServiceRequestService
from src.app.observability.logging import get_logger

logger = get_logger("payments_handler")
router = Router(name="payments")
academic_engine = AcademicServiceEngine()


@router.callback_query(F.data.startswith("pay:go:") | F.data.startswith("pay:"))
async def cb_send_stars_invoice(callback: CallbackQuery, current_user: User, session: AsyncSession):
    parts = callback.data.split(":")
    order_id_str = parts[-1]
    try:
        order_id = uuid.UUID(order_id_str)
    except ValueError:
        await callback.answer(ERROR_MESSAGES["E-02"], show_alert=True)
        return

    order = await OrderService.get_order_by_id(session, order_id)
    if not order:
        await callback.answer(ERROR_MESSAGES["E-03"], show_alert=True)
        return
    if order.user_id != current_user.user_id:
        await callback.answer(ERROR_MESSAGES["E-12"], show_alert=True)
        return

    if order.status != "pending_payment":
        await callback.answer(f"حالة الطلب الحالية: {order.status}", show_alert=True)
        return

    # Check if order is free
    if not order.payment_required or order.total_minor == 0:
        await _process_free_order(callback, order, session)
        return

    prices = [LabeledPrice(label="الخدمة الأكاديمية", amount=order.total_minor)]
    payload = f"order:{order.id}"

    service_name = order.items[0].product_title_snapshot if order.items else "الخدمة الأكاديمية"

    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"طلب #{str(order.id)[:8].upper()}",
        description=f"دفع رسوم {service_name} عبر Telegram Stars بأمان فوري.",
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token="",  # Blank for Telegram Stars
    )
    await callback.answer()


async def _process_free_order(callback: CallbackQuery, order, session: AsyncSession):
    order.status = "paid"
    await session.commit()
    text = (
        f"تم اعتماد الطلب المجاني #{str(order.id)[:8].upper()}.\n\n"
        "الخطوة التالية: أرسل الآن تفاصيل سؤالك أو المفهوم أو المسألة التي تود معالجتها:"
    )
    await callback.message.edit_text(text, reply_markup=footer_keyboard("home:menu"))
    await callback.message.answer("أرسل تفاصيل الطلب الآن.", reply_markup=persistent_reply_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("pay:free:") | F.data.startswith("confirm_free:"))
async def cb_free_order_confirm(callback: CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    parts = callback.data.split(":")
    try:
        order_id = uuid.UUID(parts[-1])
    except (ValueError, IndexError):
        await callback.answer(ERROR_MESSAGES["E-02"], show_alert=True)
        return
    order = await OrderService.get_order_by_id(session, order_id)
    if not order or order.user_id != current_user.user_id:
        await callback.answer(ERROR_MESSAGES["E-03"], show_alert=True)
        return
    if order.status != "pending_payment" or order.total_minor != 0:
        await callback.answer("هذا الطلب غير مؤهل للتفعيل المجاني.", show_alert=True)
        return

    order.status = "paid"
    await session.commit()

    await state.set_state(ServiceInputFSM.wait_text)
    await state.update_data(order_id=str(order.id))

    receipt_text = PAYMENT_RECEIPT_TEMPLATE.format(
        order_ref=str(order.id)[:8].upper(),
        service_title=order.items[0].product_title_snapshot if order.items else "خدمة مجانية",
        amount=0,
        telegram_payment_charge_id="FREE_PROMO",
        next_step_text="بدأ تجهيز طلبك. أرسل الآن سؤالك أو الموضوع لنبدأ التنفيذ مباشرة.",
    )
    await callback.message.answer(receipt_text)
    await callback.message.answer(
        "أرسل الآن نص سؤالك أو استفسارك بالتفصيل:",
        reply_markup=cancel_reply_keyboard(),
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
async def handle_successful_payment(message: Message, current_user: User, state: FSMContext, session: AsyncSession):
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
        invoice_payload=payload,
        payer_user_id=current_user.user_id,
    )

    order = await OrderService.get_order_by_id(session, order_id)
    service_title = order.items[0].product_title_snapshot if order and order.items else "خدمة تعليمية"

    # Strict §6.4 Payment Receipt (NO EMOJIS)
    receipt_text = PAYMENT_RECEIPT_TEMPLATE.format(
        order_ref=str(order_id)[:8].upper(),
        service_title=service_title,
        amount=sp.total_amount,
        telegram_payment_charge_id=sp.telegram_payment_charge_id,
        next_step_text="بدأ تجهيز طلبك. أرسل الآن بيانات ومحتوى سؤالك لنباشر التنفيذ.",
    )
    await message.answer(receipt_text)

    await state.set_state(ServiceInputFSM.wait_text)
    await state.update_data(order_id=str(order_id))

    await message.answer(
        "✍️ <b>أرسل الآن نص سؤالك أو المفهوم أو المسألة التي تود شرحها:</b>\n"
        "<i>الحد الأقصى: 2000 حرف. ويمكنك إرسال ملف توضيحي داعم إن دعت الحاجة.</i>",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="HTML",
    )


# Handlers for Service Inputs (F4 §7.4)
@router.message(ServiceInputFSM.wait_text)
async def handle_service_input_text(message: Message, current_user: User, state: FSMContext, session: AsyncSession):
    prompt_text = (message.text or "").strip()
    if not prompt_text:
        await message.answer("يرجى إرسال نص السؤال أو المفهوم.")
        return

    if len(prompt_text) > 2000:
        await message.answer(
            ERROR_MESSAGES["E-01"].format(field="النص", reason_short="تجاوز الحد الأقصى", limit_text="2000 حرف"),
        )
        return

    # Academic Integrity Check (§11 AC-01 to AC-04)
    violations = AcademicIntegrityFilter.check_prompt(prompt_text)
    if violations:
        violation_type = violations[0]
        if "exam" in violation_type or "test" in violation_type:
            ac_msg = ACADEMIC_INTEGRITY_MESSAGES["AC-01"]
        elif "essay" in violation_type or "thesis" in violation_type:
            ac_msg = ACADEMIC_INTEGRITY_MESSAGES["AC-02"]
        elif "citation" in violation_type:
            ac_msg = ACADEMIC_INTEGRITY_MESSAGES["AC-04"]
        else:
            ac_msg = ACADEMIC_INTEGRITY_MESSAGES["AC-03"]

        await message.answer(f"⚠ {ac_msg}\n\nيرجى إعادة صياغة طلبك كطلب شرح وتوجيه تعليمي.")
        return

    data = await state.get_data()
    order_id_str = data.get("order_id")

    order = None
    if order_id_str:
        try:
            order = await OrderService.get_order_by_id(session, uuid.UUID(order_id_str))
        except ValueError:
            order = None

    if not order or order.user_id != current_user.user_id or order.status != "paid":
        await state.clear()
        await message.answer("تعذر التحقق من الطلب المدفوع. يرجى بدء طلب جديد من الكتالوج.")
        return
    if not order.items or not order.items[0].service_definition_id:
        await state.clear()
        await message.answer("هذا الطلب لا يحتوي على خدمة قابلة للتنفيذ.")
        return

    order_ref = str(order.id)[:8].upper() if order else "DIRECT"
    service_name = order.items[0].product_title_snapshot if order and order.items else "خدمة تعليمية"

    # Send Acknowledgement card §6.5
    ack_text = ACKNOWLEDGEMENT_CARD_TEMPLATE.format(
        order_ref=order_ref,
        status_ar="قيد التنفيذ والتجهيز",
        sla_text="خلال دقيقة واحدة",
    )
    ack_msg = await message.answer(ack_text)

    try:
        await ServiceRequestService.submit_request(
            session=session,
            order=order,
            service_id=order.items[0].service_definition_id,
            prompt_text=prompt_text,
            title=service_name,
        )
        await session.commit()
        await state.clear()
    except Exception as exc:
        await session.rollback()
        logger.error("Could not enqueue paid service request", exc_info=exc)
        await ack_msg.delete()
        await message.answer("تعذر تسجيل الطلب مؤقتاً. لم يتم تغيير حالة الدفع، يرجى المحاولة مرة أخرى.")
        return

    await ack_msg.delete()
    await message.answer(
        f"تم تسجيل طلبك #{order_ref} وإرساله إلى طابور التنفيذ الآمن. "
        "ستصلك بطاقة التسليم عند اكتمال المعالجة.",
        reply_markup=persistent_reply_keyboard(),
    )
