from celery import Celery

from app.config import settings

celery_app = Celery("mailgenius")

celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_queues={
        "send": {"exchange": "send", "routing_key": "send"},
        "track": {"exchange": "track", "routing_key": "track"},
        "report": {"exchange": "report", "routing_key": "report"},
        "default": {"exchange": "default", "routing_key": "default"},
        "dead_letter": {"exchange": "dead_letter", "routing_key": "dead_letter"},
    },
    beat_schedule={
        "check-scheduled-campaigns": {
            "task": "app.worker.tasks.campaign_tasks.check_scheduled_campaigns",
            "schedule": 60.0,
            "options": {"queue": "default"},
        },
        "health-check-channels": {
            "task": "app.worker.tasks.send_tasks.health_check_channels",
            "schedule": 300.0,
            "options": {"queue": "default"},
        },
        "aggregate-hourly-reports": {
            "task": "app.worker.tasks.report_tasks.aggregate_pending_reports",
            "schedule": 3600.0,
            "options": {"queue": "report"},
        },
    },
)

celery_app.autodiscover_tasks(["app.worker.tasks"])
