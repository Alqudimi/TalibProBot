import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.modules.audit.models import AuditEvent
from src.app.observability.logging import get_logger

logger = get_logger("audit")


class AuditService:
    """Service logging tamper-evident append-only domain audit events."""

    @staticmethod
    async def log_event(
        session: AsyncSession,
        action_code: str,
        entity_type: str,
        actor_user_id: Optional[uuid.UUID] = None,
        entity_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        target_kind: Optional[str] = None,
        target_id: Optional[str] = None,
        outcome: str = "success",
        request_id: Optional[str] = None,
        change_summary: Optional[dict] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=uuid.uuid4(),
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action_code=action_code,
            entity_type=entity_type,
            entity_id=entity_id,
            target_kind=target_kind,
            target_id=target_id,
            outcome=outcome,
            request_id=request_id,
            change_summary=change_summary or {},
        )
        session.add(event)
        await session.flush()
        logger.info(f"Audit event recorded: {action_code} on {entity_type} {entity_id} by {actor_user_id}")
        return event
