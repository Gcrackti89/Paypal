from __future__ import annotations
from celery import Celery
from backend.config import settings

celery_app = Celery(
    "recoveriq",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.config_from_object({
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "UTC",
    "enable_utc": True,
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
    "task_routes": {
        "backend.tasks.*": {"queue": "default"},
        "backend.tasks.process_webhook_event": {"queue": settings.WEBHOOK_PROCESSING_QUEUE},
    },
    "beat_schedule": {
        "scheduled-recovery-scan": {
            "task": "backend.tasks.scheduled_recovery_scan",
            "schedule": 3600.0,  # every hour
        },
        "scheduled-reconciliation": {
            "task": "backend.tasks.scheduled_reconciliation",
            "schedule": 1800.0,  # every 30 minutes
        },
    },
})

celery_app.autodiscover_tasks(["backend"])
