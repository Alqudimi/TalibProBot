import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Coroutine, Dict, Optional
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.observability.logging import get_logger

logger = get_logger("outbox")

TaskHandler = Callable[[Dict[str, Any], AsyncSession], Coroutine[Any, Any, None]]
_TASK_HANDLERS: Dict[str, TaskHandler] = {}


def register_task_handler(event_type: str) -> Callable[[TaskHandler], TaskHandler]:
    """Decorator to register a worker task handler for an event type."""
    def decorator(func: TaskHandler) -> TaskHandler:
        _TASK_HANDLERS[event_type] = func
        return func
    return decorator


async def enqueue_outbox_event(
    session: AsyncSession,
    event_type: str,
    aggregate_type: str,
    aggregate_id: UUID,
    payload: Dict[str, Any],
    organization_id: Optional[UUID] = None,
    event_key: Optional[str] = None,
) -> UUID:
    """Inserts a transactional outbox task within the current DB transaction."""
    import uuid
    if not event_key:
        event_key = f"{event_type}:{aggregate_id}:{uuid.uuid4().hex[:8]}"

    query = text(
        """
        INSERT INTO student_platform.transactional_outbox
            (id, event_key, event_type, aggregate_type, aggregate_id, organization_id, payload, status, attempt_count, available_at)
        VALUES
            (:id, :event_key, :event_type, :aggregate_type, :aggregate_id, :organization_id, CAST(:payload AS jsonb), 'pending', 0, now())
        RETURNING id;
        """
    )
    task_id = uuid.uuid4()
    result = await session.execute(
        query,
        {
            "id": task_id,
            "event_key": event_key,
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "organization_id": organization_id,
            "payload": json.dumps(payload, default=str),
        },
    )
    res_id = result.scalar_one()
    logger.info(f"Enqueued outbox task #{res_id}: {event_type} for {aggregate_type} {aggregate_id}")
    return res_id


async def process_outbox_batch(session: AsyncSession, batch_size: int = 10, max_attempts: int = 5) -> int:
    """Fetches and executes pending outbox tasks using FOR UPDATE SKIP LOCKED."""
    fetch_query = text(
        """
        SELECT id, event_type, aggregate_type, aggregate_id, payload, attempt_count
        FROM student_platform.transactional_outbox
        WHERE status IN ('pending', 'retry') AND available_at <= now()
        ORDER BY available_at ASC, created_at ASC
        LIMIT :batch_size
        FOR UPDATE SKIP LOCKED;
        """
    )
    result = await session.execute(fetch_query, {"batch_size": batch_size})
    rows = result.fetchall()
    if not rows:
        return 0

    processed_count = 0
    for row in rows:
        task_id, event_type, agg_type, agg_id, raw_payload, attempts = row
        payload = raw_payload if isinstance(raw_payload, dict) else json.loads(raw_payload)
        handler = _TASK_HANDLERS.get(event_type)

        if not handler:
            logger.warning(f"No handler registered for task #{task_id} event_type '{event_type}'. Skipping.")
            continue

        try:
            logger.info(f"Processing outbox task #{task_id} ({event_type})...")
            await handler(payload, session)

            # Mark published/completed
            await session.execute(
                text(
                    """
                    UPDATE student_platform.transactional_outbox
                    SET status = 'published', published_at = now(), last_error_safe = NULL
                    WHERE id = :id;
                    """
                ),
                {"id": task_id},
            )
            processed_count += 1
            logger.info(f"Outbox task #{task_id} ({event_type}) completed successfully.")
        except Exception as e:
            new_attempts = attempts + 1
            logger.error(f"Error processing outbox task #{task_id} (attempt {new_attempts}/{max_attempts}): {e}")
            if new_attempts >= max_attempts:
                status = "dead_letter"
                next_time = datetime.now(timezone.utc) + timedelta(days=365)
            else:
                status = "retry"
                # Exponential backoff: 2^attempts * 10 seconds (10s, 20s, 40s...)
                backoff_seconds = (2 ** attempts) * 10
                next_time = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)

            safe_err = str(e)[:500]
            await session.execute(
                text(
                    """
                    UPDATE student_platform.transactional_outbox
                    SET status = :status,
                        attempt_count = :attempts,
                        available_at = :next_time,
                        last_error_safe = :error
                    WHERE id = :id;
                    """
                ),
                {
                    "status": status,
                    "attempts": new_attempts,
                    "next_time": next_time,
                    "error": safe_err,
                    "id": task_id,
                },
            )
        await session.commit()

    return processed_count

