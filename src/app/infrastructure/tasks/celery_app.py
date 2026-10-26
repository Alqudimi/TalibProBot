from celery import Celery

from src.app.config.settings import settings


def redis_url(database: int) -> str:
    password = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
    return f"redis://{password}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{database}"


celery_app = Celery(
    "talibprobot",
    broker=redis_url(settings.CELERY_BROKER_DB),
    backend=redis_url(settings.CELERY_RESULT_DB),
    include=["src.app.infrastructure.tasks.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,
)
