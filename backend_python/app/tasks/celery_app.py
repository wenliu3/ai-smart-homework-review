"""Celery 应用：Redis 只承担队列与短期结果协调。"""
from celery import Celery

from ..config import settings

celery_app = Celery(
    "ai_smart_homework_review",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.grading"],
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "agent.grading.run": {"queue": "grading"},
    },
)

__all__ = ["celery_app"]
