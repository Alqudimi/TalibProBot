"""
Telegram bot handlers for interactive Academic Services (153 Services).
Allows students to execute services directly via bot commands and interactive prompts.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.app.modules.academic_services.engine import AcademicServiceEngine
from src.app.modules.academic_services.schemas import ServiceInput
from src.app.modules.accounts.models import User
from src.app.modules.orders.models import Order, OrderItem
from src.app.modules.service_requests.service import ServiceRequestService
from src.app.observability.logging import get_logger

logger = get_logger("bot.handlers.services")
router = Router(name="services")
engine = AcademicServiceEngine()


class ServiceExecutionState(StatesGroup):
    waiting_for_service_code = State()
    waiting_for_content = State()


@router.message(Command("service"))
async def cmd_service_direct(message: Message, current_user: User, session: AsyncSession) -> None:
    """
    Direct invocation: /service <code> <content>
    Example: /service 001 قانون نيوتن الثاني
    """
    parts = message.text.split(maxsplit=2) if message.text else []
    if len(parts) < 3:
        await message.answer(
            "ℹ️ <b>طريقة استخدام أمر الخدمة المباشر:</b>\n"
            "<code>/service &lt;رقم_الخدمة&gt; &lt;السؤال أو الموضوع&gt;</code>\n\n"
            "<b>أمثلة:</b>\n"
            "• <code>/service 001 قانون الجاذبية العام</code> (شرح مفهوم)\n"
            "• <code>/service 002 مسألة مقاومة كهربائية</code> (تفكيك سؤال)\n"
            "• <code>/service 004 حساب المثلثات</code> (توليد أسئلة تدريبية)\n"
            "• <code>/service 009 التفاضل والتكامل</code> (خطة مراجعة)\n\n"
            "أو استخدم الأمر <code>/catalog</code> لتصفح قائمة الخدمات."
        )
        return

    service_code = parts[1].strip().zfill(3)
    content = parts[2].strip()

    stmt = (
        select(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .options(selectinload(Order.items))
        .where(
            Order.user_id == current_user.user_id,
            Order.status == "paid",
            OrderItem.product_code_snapshot == service_code,
        )
        .order_by(Order.created_at.desc())
        .limit(1)
    )
    order = (await session.execute(stmt)).unique().scalar_one_or_none()
    if not order or not order.items or not order.items[0].service_definition_id:
        await message.answer(
            "لا يمكن تنفيذ الخدمة مباشرة. يرجى اختيار الخدمة من الكتالوج وإتمام الطلب أولاً.",
        )
        return

    item = next((i for i in order.items if i.product_code_snapshot == service_code), order.items[0])
    await ServiceRequestService.submit_request(
        session=session,
        order=order,
        service_id=item.service_definition_id,
        prompt_text=content,
        title=item.product_title_snapshot,
    )
    await session.commit()
    await message.answer(
        f"تم استلام طلبك المدفوع للخدمة {service_code} ووضعه في طابور التنفيذ الآمن. "
        "ستصلك النتيجة بعد اكتمال المعالجة.",
    )


@router.message(Command("explain"))
async def cmd_explain(message: Message, current_user: User, session: AsyncSession) -> None:
    """Shortcut for Service 001 (Concept Explainer)."""
    concept = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    if not concept:
        await message.answer("ℹ️ اكتب المفهوم بعد الأمر، مثال:\n<code>/explain ظاهرة الرنين المغناطيسي</code>")
        return

    stmt = (
        select(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .options(selectinload(Order.items))
        .where(
            Order.user_id == current_user.user_id,
            Order.status == "paid",
            OrderItem.product_code_snapshot == "001",
        )
        .order_by(Order.created_at.desc())
        .limit(1)
    )
    order = (await session.execute(stmt)).unique().scalar_one_or_none()
    if not order or not order.items or not order.items[0].service_definition_id:
        await message.answer("يرجى شراء خدمة الشرح من الكتالوج قبل استخدام هذا الأمر.")
        return
    item = next((i for i in order.items if i.product_code_snapshot == "001"), order.items[0])
    await ServiceRequestService.submit_request(
        session=session,
        order=order,
        service_id=item.service_definition_id,
        prompt_text=concept,
        title=item.product_title_snapshot,
    )
    await session.commit()
    await message.answer("تم تسجيل طلب الشرح المدفوع وإرساله إلى طابور التنفيذ.")


@router.callback_query(F.data.startswith("srv_act:"))
async def handle_service_action(callback: CallbackQuery) -> None:
    """Handle follow-up button clicks for executed services."""
    parts = callback.data.split(":")
    service_code = parts[1]
    action = parts[2]

    await callback.answer(f"تم اختيار: {action}")
    await callback.message.reply(f"💡 تم استلام طلب المتابعة ({action}) للخدمة {service_code}. جارٍ التحديث...")
