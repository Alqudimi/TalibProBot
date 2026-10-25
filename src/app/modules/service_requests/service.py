import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.infrastructure.queue.outbox import enqueue_outbox_event
from src.app.modules.delivery.models import Delivery
from src.app.modules.orders.models import Order
from src.app.modules.service_requests.models import ServiceRequest
from src.app.observability.logging import get_logger
from src.app.shared.errors import AcademicIntegrityViolationError, OrderInvalidStateError

logger = get_logger("service_requests")

# Academic integrity keywords that indicate direct cheating attempt
ACADEMIC_CHEATING_KEYWORDS = [
    re.compile(r"حل\s+(لي\s+)?(.*\s+)?(اختبار|امتحان|كويز|فاينل|ميدتيرم|واجب كامل).*(الآن|حالي|مباشر|فوري)", re.IGNORECASE),
    re.compile(r"(ادخل|حل|امتحن|اختبر|احضر)\s+(عني|بدلي|بدلا مني|مكاني).*(الاختبار|الامتحان|الكويز|المقابلة|التقييم|الأسئلة)", re.IGNORECASE),
    re.compile(r"تسريب\s+.*(اسئلة|امتحان|اختبار|كويز)", re.IGNORECASE),
    re.compile(r"(اكتب|سوي|اعمل)\s+(لي\s+)?(بحث|مشروع|تقرير)\s+(كامل\s+)?(عني|باسمي)\s+(لأقدمه|لتسليمه)", re.IGNORECASE),
    re.compile(r"(قاعة|أثناء|وقت)\s+.*(اختبار|امتحان|كويز)", re.IGNORECASE),
    re.compile(r"حل\s+.*(لتسليمه|تسليمه)\s+(فوراً|فورا|مباشرة|الآن)", re.IGNORECASE),
]



class AcademicIntegrityFilter:
    """Helper filter for screening prompts for academic integrity."""

    @staticmethod
    def validate_request(prompt_text: str) -> tuple[bool, str]:
        if not prompt_text:
            return True, ""
        for pattern in ACADEMIC_CHEATING_KEYWORDS:
            if pattern.search(prompt_text):
                return False, (
                    "نعتذر، تمنع سياسة النزاهة الأكاديمية حل الاختبارات الرسمية نيابة عن الطالب أو إنجاز الواجبات المباشرة. "
                    "يمكنك طلب شرح المفاهيم، تفكيك خطوات الحل، أو التدرب على أسئلة مشابهة."
                )
        return True, ""


class ServiceRequestService:
    """Service handling student requests, academic integrity verification, and fulfillment delivery."""

    @staticmethod
    def screen_academic_integrity(prompt_text: str) -> None:
        """Enforces academic integrity rules: blocks direct exam solving or exam cheating."""
        is_safe, reason = AcademicIntegrityFilter.validate_request(prompt_text)
        if not is_safe:
            logger.warning(f"Academic integrity violation flagged for prompt: {prompt_text[:100]}")
            raise AcademicIntegrityViolationError(reason)

    @staticmethod
    async def submit_request(
        session: AsyncSession,
        order: Order,
        service_id: uuid.UUID,
        prompt_text: str,
        title: str = "طلب خدمة تعليمية",
    ) -> ServiceRequest:
        """Validates order status and creates a service execution request."""
        if order.status != "paid":
            raise OrderInvalidStateError("Cannot fulfill a service request for an unpaid order.")

        # Academic integrity check
        ServiceRequestService.screen_academic_integrity(prompt_text)

        request = ServiceRequest(
            id=uuid.uuid4(),
            order_id=order.id,
            user_id=order.user_id,
            service_id=service_id,
            status="submitted",
            title=title[:255],
            prompt_text=prompt_text,
        )
        session.add(request)
        await session.flush()

        # Enqueue background execution task
        await enqueue_outbox_event(
            session=session,
            event_type="service.execute",
            aggregate_type="service_request",
            aggregate_id=request.id,
            payload={
                "request_id": str(request.id),
                "order_id": str(order.id),
                "user_id": str(order.user_id),
                "service_id": str(service_id),
                "prompt": prompt_text,
            },
        )
        logger.info(f"Service request {request.id} created and enqueued for execution.")
        return request

    @staticmethod
    async def deliver_result(
        session: AsyncSession,
        request_id: uuid.UUID,
        deliverable_content: dict,
    ) -> Delivery:
        """Records final deliverable and marks the request delivered."""
        stmt = select(ServiceRequest).where(ServiceRequest.id == request_id)
        result = await session.execute(stmt)
        request = result.scalar_one_or_none()
        if not request:
            raise ValueError(f"Service request {request_id} not found.")

        import json
        from src.app.modules.files.service import FileStorageService

        storage_key = f"deliveries/{request.id}_{uuid.uuid4().hex[:8]}.json"
        content_bytes = json.dumps(deliverable_content).encode("utf-8")
        asset = await FileStorageService.register_asset(
            session=session,
            owner_user_id=request.user_id,
            storage_key=storage_key,
            media_type="application/json",
            byte_size=len(content_bytes),
            asset_kind="request_output",
        )

        delivery = Delivery(
            id=uuid.uuid4(),
            service_request_id=request.id,
            asset_id=asset.id,
            idempotency_key=f"delivery:req:{request.id}",
            status="delivered",
            available_at=datetime.now(timezone.utc),
            first_delivered_at=datetime.now(timezone.utc),
        )
        session.add(delivery)

        request.status = "delivered"
        request.updated_at = datetime.now(timezone.utc)
        await session.flush()

        # Enqueue customer notification task
        await enqueue_outbox_event(
            session=session,
            event_type="service.delivered",
            aggregate_type="delivery",
            aggregate_id=delivery.id,
            payload={
                "delivery_id": str(delivery.id),
                "user_id": str(request.user_id),
                "request_id": str(request.id),
                "title": request.title,
            },
        )
        logger.info(f"Delivered result for request {request.id} with delivery #{delivery.id}")
        return delivery
