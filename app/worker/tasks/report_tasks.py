import uuid
from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import select, func

from app.worker.celery_app import celery_app
from app.worker.db import SyncSessionFactory
from app.models.campaign import Campaign
from app.models.report import CampaignReport
from app.models.tracking import TrackingEvent

logger = get_task_logger(__name__)


@celery_app.task(queue="report")
def aggregate_campaign_report(campaign_id: str, report_type: str = "hourly"):
    with SyncSessionFactory() as db:
        campaign = db.execute(
            select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        ).scalar_one_or_none()
        if not campaign:
            return

        now = datetime.now(timezone.utc)
        metrics = {
            "total_recipients": campaign.total_recipients,
            "sent": campaign.sent_count,
            "delivered": campaign.sent_count - campaign.bounced_count,
            "opened": campaign.opened_count,
            "clicked": campaign.clicked_count,
            "bounced": campaign.bounced_count,
            "unsubscribed": campaign.unsubscribed_count,
            "failed": campaign.failed_count,
        }

        total = campaign.total_recipients or 1
        funnel = {
            "sent": campaign.sent_count,
            "delivered": campaign.sent_count - campaign.bounced_count,
            "opened": campaign.opened_count,
            "clicked": campaign.clicked_count,
            "converted": 0,
            "delivery_rate": round((campaign.sent_count - campaign.bounced_count) / total * 100, 2),
            "open_rate": round(campaign.opened_count / total * 100, 2),
            "click_rate": round(campaign.clicked_count / total * 100, 2),
        }

        report = CampaignReport(
            tenant_id=campaign.tenant_id,
            campaign_id=campaign.id,
            report_type=report_type,
            period_end=now,
            metrics=metrics,
            funnel=funnel,
        )
        db.add(report)
        db.commit()


@celery_app.task(queue="report")
def aggregate_pending_reports():
    with SyncSessionFactory() as db:
        # Aggregate reports for all active/recently completed campaigns
        campaigns = db.execute(
            select(Campaign).where(
                Campaign.status.in_(["sending", "completed"]),
                Campaign.sent_count > 0,
            )
        ).scalars().all()

        for campaign in campaigns:
            aggregate_campaign_report.delay(str(campaign.id), "hourly")
