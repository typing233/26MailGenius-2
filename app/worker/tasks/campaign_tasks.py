import math
import uuid
from datetime import datetime, timezone

from app.worker.celery_app import celery_app
from app.worker.db import SyncSessionFactory
from app.models.campaign import Campaign, CampaignJob
from app.models.segment import SegmentRule
from app.models.subscriber import Subscriber
from app.models.mailing_list import ListSubscriber
from app.models.suppression import SuppressionEntry
from sqlalchemy import select, func, update


def _evaluate_segment_sync(db, tenant_id: uuid.UUID, conditions: list[dict]) -> set[uuid.UUID]:
    """Evaluate segment conditions synchronously and return matching subscriber IDs."""
    from sqlalchemy import and_

    base_filters = [
        Subscriber.tenant_id == tenant_id,
        Subscriber.deleted_at.is_(None),
        Subscriber.status == "confirmed",
    ]

    condition_filters = []
    for cond in conditions:
        field = cond.get("field")
        operator = cond.get("operator")
        value = cond.get("value")
        clause = _build_condition(field, operator, value)
        if clause is not None:
            condition_filters.append(clause)

    stmt = select(Subscriber.id).where(*base_filters, *condition_filters)
    rows = db.execute(stmt).all()
    return {r[0] for r in rows}


def _build_condition(field: str, operator: str, value):
    """Build a single SQLAlchemy filter clause for a segment condition."""
    if field == "email":
        col = Subscriber.email
    elif field == "name":
        col = Subscriber.name
    elif field == "status":
        col = Subscriber.status
    elif field == "source":
        col = Subscriber.source
    elif field.startswith("custom_fields."):
        json_path = field.replace("custom_fields.", "")
        col = Subscriber.custom_fields[json_path].astext
    elif field == "tags":
        if operator == "contains":
            return Subscriber.tags.contains([value])
        return None
    else:
        return None

    if operator == "eq":
        return col == value
    elif operator == "neq":
        return col != value
    elif operator == "contains":
        return col.ilike(f"%{value}%")
    elif operator == "starts_with":
        return col.ilike(f"{value}%")
    elif operator == "in":
        return col.in_(value if isinstance(value, list) else [value])
    elif operator == "not_in":
        return col.notin_(value if isinstance(value, list) else [value])
    return None


@celery_app.task(queue="default")
def prepare_campaign(campaign_id: str):
    with SyncSessionFactory() as db:
        campaign = db.execute(
            select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        ).scalar_one_or_none()
        if not campaign or campaign.status != "sending":
            return

        subscriber_ids: set[uuid.UUID] = set()

        # From lists
        if campaign.list_ids:
            rows = db.execute(
                select(ListSubscriber.subscriber_id).where(
                    ListSubscriber.list_id.in_(campaign.list_ids),
                    ListSubscriber.unsubscribed_at.is_(None),
                )
            ).all()
            subscriber_ids.update(r[0] for r in rows)

        # From segment rules
        if campaign.segment_rule_ids:
            for seg_id in campaign.segment_rule_ids:
                segment = db.execute(
                    select(SegmentRule).where(
                        SegmentRule.id == seg_id,
                        SegmentRule.tenant_id == campaign.tenant_id,
                        SegmentRule.deleted_at.is_(None),
                    )
                ).scalar_one_or_none()
                if segment and segment.conditions:
                    matched = _evaluate_segment_sync(db, campaign.tenant_id, segment.conditions)
                    subscriber_ids.update(matched)

        # Exclusion lists
        if campaign.exclusion_list_ids:
            rows = db.execute(
                select(ListSubscriber.subscriber_id).where(
                    ListSubscriber.list_id.in_(campaign.exclusion_list_ids),
                    ListSubscriber.unsubscribed_at.is_(None),
                )
            ).all()
            subscriber_ids -= {r[0] for r in rows}

        # Suppression list
        suppressed = db.execute(
            select(SuppressionEntry.email).where(
                SuppressionEntry.tenant_id == campaign.tenant_id,
            )
        ).all()
        if suppressed:
            suppressed_emails = {r[0] for r in suppressed}
            if subscriber_ids:
                suppressed_sub_ids = db.execute(
                    select(Subscriber.id).where(
                        Subscriber.id.in_(list(subscriber_ids)),
                        Subscriber.email.in_(suppressed_emails),
                    )
                ).all()
                subscriber_ids -= {r[0] for r in suppressed_sub_ids}

        # Filter to confirmed, non-deleted subscribers only
        if subscriber_ids:
            valid = db.execute(
                select(Subscriber.id).where(
                    Subscriber.id.in_(list(subscriber_ids)),
                    Subscriber.tenant_id == campaign.tenant_id,
                    Subscriber.status == "confirmed",
                    Subscriber.deleted_at.is_(None),
                )
            ).all()
            subscriber_ids = {r[0] for r in valid}

        # Create campaign jobs in batches
        batch_size = campaign.batch_size or 500
        sorted_ids = sorted(subscriber_ids)
        jobs = []
        for i, sub_id in enumerate(sorted_ids):
            batch_num = i // batch_size
            job = CampaignJob(
                tenant_id=campaign.tenant_id,
                campaign_id=campaign.id,
                subscriber_id=sub_id,
                batch_number=batch_num,
                status="pending",
                idempotency_key=f"{campaign.id}:{sub_id}",
            )
            jobs.append(job)

        db.add_all(jobs)
        campaign.total_recipients = len(jobs)
        db.commit()

        # Start dispatching
        dispatch_batches.delay(campaign_id)


@celery_app.task(queue="default")
def dispatch_batches(campaign_id: str):
    with SyncSessionFactory() as db:
        campaign = db.execute(
            select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        ).scalar_one_or_none()
        if not campaign:
            return
        if campaign.status in ("paused", "cancelled"):
            return
        if campaign.status == "completed":
            return

        # Find next pending batch
        next_batch = db.execute(
            select(func.min(CampaignJob.batch_number)).where(
                CampaignJob.campaign_id == campaign.id,
                CampaignJob.status == "pending",
            )
        ).scalar()

        if next_batch is None:
            # All batches done
            campaign.status = "completed"
            campaign.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # Get jobs in this batch
        jobs = db.execute(
            select(CampaignJob).where(
                CampaignJob.campaign_id == campaign.id,
                CampaignJob.batch_number == next_batch,
                CampaignJob.status == "pending",
            )
        ).scalars().all()

        from app.worker.tasks.send_tasks import send_email

        for job in jobs:
            job.status = "queued"
            send_email.apply_async(args=[str(job.id)], queue="send")

        db.commit()

        # Schedule next batch after interval
        interval = campaign.batch_interval_seconds or 10
        dispatch_batches.apply_async(
            args=[campaign_id],
            countdown=interval,
            queue="default",
        )


@celery_app.task(queue="default")
def check_scheduled_campaigns():
    with SyncSessionFactory() as db:
        now = datetime.now(timezone.utc)
        campaigns = db.execute(
            select(Campaign).where(
                Campaign.status == "scheduled",
                Campaign.scheduled_at <= now,
            )
        ).scalars().all()

        for campaign in campaigns:
            campaign.status = "sending"
            campaign.started_at = now
            db.commit()
            prepare_campaign.delay(str(campaign.id))
