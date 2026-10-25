import asyncio
import uuid
from typing import Any, Dict
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.config.settings import settings
from src.app.infrastructure.database.session import get_db_session
from src.app.infrastructure.queue.outbox import process_outbox_batch, register_task_handler
from src.app.modules.accounts.models import ExternalIdentity, User
from src.app.modules.orders.models import Order
from src.app.modules.service_requests.service import ServiceRequestService
from src.app.modules.subscriptions.service import SubscriptionService
from src.app.observability.logging import get_logger

logger = get_logger("worker")
_bot: Bot | None = None


def get_worker_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=settings.BOT_TOKEN)
    return _bot


@register_task_handler("order.paid")
async def handle_order_paid(payload: Dict[str, Any], session: AsyncSession) -> None:
    order_id = uuid.UUID(payload["order_id"])
    user_id = uuid.UUID(payload["user_id"])
    amount = payload.get("amount", 0)
    currency = payload.get("currency", "XTR")

    logger.info(f"Worker handling 'order.paid' for order {order_id} (user {user_id})")

    # Load order items to see if subscription offer
    stmt = select(Order).where(Order.id == order_id)
    res = await session.execute(stmt)
    order = res.scalar_one_or_none()
    if not order:
        return

    # If subscription or recurring
    for item in order.items:
        await SubscriptionService.activate_subscription(
            session=session,
            user_id=user_id,
            offer_id=item.offer_id,
            currency_code=currency,
            price_minor=amount,
            duration_days=30,
            entitlement_ids=["question_bank", "study_plan"],
        )


@register_task_handler("service.execute")
async def handle_service_execute(payload: Dict[str, Any], session: AsyncSession) -> None:
    request_id = uuid.UUID(payload["request_id"])
    prompt = payload.get("prompt", "")

    logger.info(f"Worker generating educational result for request {request_id}...")

    # Build pedagogical structured explanation
    deliverable_payload = {
        "title": "الشرح التعليمي وتفكيك خطوات الحل",
        "concept_breakdown": f"تم تحليل المفهوم المتعلق بـ: '{prompt[:60]}'.",
        "guided_steps": [
            "الخطوة 1: تحديد المعطيات الأساسية والمطلوب في السؤال بدقة.",
            "الخطوة 2: استدعاء القوانين والمفاهيم النظرية الحاكمة للمسألة.",
            "الخطوة 3: تطبيق خطوات الحل بتسلسل منطقي.",
            "الخطوة 4: التحقق من صحة النتيجة والوحدات المستخدمة.",
        ],
        "practice_question": "سؤال تدريبي مقترح للتحقق من الفهم: جرب تطبيق نفس الخطوات السابقة على حالة مشابهة.",
        "academic_note": "هذا المحتوى مقدم لأغراض تعليمية لمساعدتك على إتقان مهارة حل المسائل بأنماطها المختلفة.",
    }

    await ServiceRequestService.deliver_result(
        session=session,
        request_id=request_id,
        deliverable_content=deliverable_payload,
    )


@register_task_handler("service.delivered")
async def handle_service_delivered(payload: Dict[str, Any], session: AsyncSession) -> None:
    user_id = uuid.UUID(payload["user_id"])
    title = payload.get("title", "طلبك الدراسي")

    # Look up user's telegram ID
    stmt = (
        select(ExternalIdentity.telegram_user_id)
        .where(
            ExternalIdentity.user_id == user_id,
            ExternalIdentity.provider == "telegram",
        )
    )
    res = await session.execute(stmt)
    tg_id = res.scalar_one_or_none()

    if tg_id and settings.BOT_TOKEN and not settings.BOT_TOKEN.startswith("0000000000"):
        try:
            bot = get_worker_bot()
            text_msg = (
                f"📬 <b>تم تسليم {title} بنجاح!</b>\n\n"
                "تم إعداد وتفكيك الشرح الدراسي والخطوات المطلوبة بعناية.\n"
                "يمكنك مراجعة كافة تفاصيل التسليم عبر سجل طلباتك في البوت."
            )
            await bot.send_message(chat_id=tg_id, text=text_msg, parse_mode="HTML")
            logger.info(f"Notification sent to telegram user {tg_id}")
        except Exception as e:
            logger.warning(f"Could not send telegram message to user {tg_id}: {e}")


async def run_task_worker(poll_interval: float = 2.0, run_once: bool = False) -> None:
    """Continuous polling loop for outbox tasks."""
    logger.info("Starting Background Task Worker...")
    while True:
        try:
            async with get_db_session() as session:
                processed = await process_outbox_batch(session=session, batch_size=10)
                if processed > 0:
                    logger.info(f"Worker processed {processed} tasks in batch.")
        except Exception as e:
            logger.error(f"Worker loop error: {e}")

        if run_once:
            break
        await asyncio.sleep(poll_interval)
