"""
Telegram bot handlers for interactive Academic Services (153 Services).
Allows students to execute services directly via bot commands and interactive prompts.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.academic_services.engine import AcademicServiceEngine
from src.app.modules.academic_services.schemas import ServiceInput
from src.app.observability.logging import get_logger

logger = get_logger("bot.handlers.services")
router = Router(name="services")
engine = AcademicServiceEngine()


class ServiceExecutionState(StatesGroup):
    waiting_for_service_code = State()
    waiting_for_content = State()


@router.message(Command("service"))
async def cmd_service_direct(message: Message, session: AsyncSession) -> None:
    """
    Direct invocation: /service <code> <content>
    Example: /service 001 قانون نيوتن الثاني
    """
    user = getattr(message, "middleware_user", None)
    user_id = str(user.id) if user else "00000000-0000-0000-0000-000000000000"

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

    await message.answer(f"⏳ <i>جارٍ معالجة طلبك للخدمة ({service_code})...</i>")

    inp = ServiceInput(
        service_code=service_code,
        user_id=user_id,
        content=content
    )

    result = await engine.execute_service(inp)

    # Build keyboard if follow-up actions exist
    keyboard = None
    if result.follow_up_actions:
        buttons = [
            [InlineKeyboardButton(text=act["label"], callback_data=f"srv_act:{service_code}:{act['action']}")]
            for act in result.follow_up_actions
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(result.rendered_output, reply_markup=keyboard)


@router.message(Command("explain"))
async def cmd_explain(message: Message) -> None:
    """Shortcut for Service 001 (Concept Explainer)."""
    concept = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    if not concept:
        await message.answer("ℹ️ اكتب المفهوم بعد الأمر، مثال:\n<code>/explain ظاهرة الرنين المغناطيسي</code>")
        return

    user = getattr(message, "middleware_user", None)
    user_id = str(user.id) if user else "00000000-0000-0000-0000-000000000000"

    inp = ServiceInput(service_code="001", user_id=user_id, content=concept)
    result = await engine.execute_service(inp)
    await message.answer(result.rendered_output)


@router.callback_query(F.data.startswith("srv_act:"))
async def handle_service_action(callback: CallbackQuery) -> None:
    """Handle follow-up button clicks for executed services."""
    parts = callback.data.split(":")
    service_code = parts[1]
    action = parts[2]

    await callback.answer(f"تم اختيار: {action}")
    await callback.message.reply(f"💡 تم استلام طلب المتابعة ({action}) للخدمة {service_code}. جارٍ التحديث...")
