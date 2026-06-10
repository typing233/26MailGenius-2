import hashlib
import uuid
from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import select, update

from app.worker.celery_app import celery_app
from app.worker.db import SyncSessionFactory
from app.models.campaign import Campaign
from app.models.suppression import SuppressionEntry
from app.models.subscriber import Subscriber
from app.models.tracking import TrackingEvent, TrackingLink

logger = get_task_logger(__name__)


@celery_app.task(queue="track")
def record_tracking_event(event_data: dict):
    with SyncSessionFactory() as db:
        tenant_id = uuid.UUID(event_data["tenant_id"])
        campaign_id = uuid.UUID(event_data["campaign_id"])
        subscriber_id = uuid.UUID(event_data["subscriber_id"])
        event_type = event_data["event_type"]
        job_id = uuid.UUID(event_data["job_id"]) if event_data.get("job_id") else None
        link_url = event_data.get("link_url")
        user_agent = event_data.get("user_agent", "")
        ip_address = event_data.get("ip_address")

        # Compute fingerprint for dedup
        now = datetime.now(timezone.utc)
        hour_bucket = now.strftime("%Y-%m-%dT%H")
        url_hash = hashlib.md5((link_url or "").encode()).hexdigest()[:8]
        fingerprint = f"{campaign_id}:{subscriber_id}:{event_type}:{url_hash}:{hour_bucket}"

        # Check dedup
        existing = db.execute(
            select(TrackingEvent.id).where(TrackingEvent.fingerprint == fingerprint)
        ).scalar_one_or_none()
        if existing:
            return

        # Detect machine opens (Apple MPP, etc.)
        is_machine = False
        if event_type == "open" and user_agent:
            ua_lower = user_agent.lower()
            if "fetchmail" in ua_lower or "apple mail" in ua_lower or "cfnetwork" in ua_lower:
                is_machine = True

        # Check if this is the first event of this type for this subscriber+campaign
        is_first = False
        if event_type in ("open", "click"):
            first_check = db.execute(
                select(TrackingEvent.id).where(
                    TrackingEvent.campaign_id == campaign_id,
                    TrackingEvent.subscriber_id == subscriber_id,
                    TrackingEvent.event_type == event_type,
                    TrackingEvent.is_first.is_(True),
                )
            ).scalar_one_or_none()
            if not first_check:
                is_first = True

        # Truncate IP for privacy
        if ip_address and "." in ip_address:
            parts = ip_address.split(".")
            ip_address = f"{parts[0]}.{parts[1]}.{parts[2]}.0"

        event = TrackingEvent(
            tenant_id=tenant_id,
            campaign_id=campaign_id,
            subscriber_id=subscriber_id,
            job_id=job_id,
            event_type=event_type,
            link_url=link_url,
            user_agent=user_agent[:500] if user_agent else None,
            ip_address=ip_address,
            fingerprint=fingerprint,
            is_first=is_first,
            is_machine=is_machine,
            occurred_at=now,
        )
        db.add(event)

        # Update campaign stats (only count non-machine events for opens)
        if not is_machine and is_first:
            if event_type == "open":
                db.execute(update(Campaign).where(Campaign.id == campaign_id).values(
                    opened_count=Campaign.opened_count + 1
                ))
            elif event_type == "click":
                db.execute(update(Campaign).where(Campaign.id == campaign_id).values(
                    clicked_count=Campaign.clicked_count + 1
                ))

        # Update tracking link click count
        if event_type == "click" and link_url:
            link = db.execute(
                select(TrackingLink).where(
                    TrackingLink.campaign_id == campaign_id,
                    TrackingLink.original_url == link_url,
                )
            ).scalar_one_or_none()
            if link:
                link.click_count += 1
                if is_first:
                    link.unique_clicks += 1

        db.commit()


@celery_app.task(queue="track")
def process_bounce(payload: dict):
    with SyncSessionFactory() as db:
        email = payload["email"]
        bounce_type = payload.get("bounce_type", "hard")

        # Find subscriber
        subscriber = db.execute(
            select(Subscriber).where(Subscriber.email == email)
        ).scalar_one_or_none()
        if not subscriber:
            return

        # Record tracking event
        if payload.get("campaign_id"):
            event = TrackingEvent(
                tenant_id=subscriber.tenant_id,
                campaign_id=uuid.UUID(payload["campaign_id"]),
                subscriber_id=subscriber.id,
                event_type="bounce",
                occurred_at=datetime.now(timezone.utc),
                fingerprint=f"bounce:{subscriber.id}:{payload.get('campaign_id')}",
            )
            db.add(event)

            # Update campaign stats
            db.execute(update(Campaign).where(
                Campaign.id == uuid.UUID(payload["campaign_id"])
            ).values(bounced_count=Campaign.bounced_count + 1))

        if bounce_type == "hard":
            # Add to suppression list
            existing = db.execute(
                select(SuppressionEntry).where(
                    SuppressionEntry.tenant_id == subscriber.tenant_id,
                    SuppressionEntry.email == email,
                )
            ).scalar_one_or_none()
            if not existing:
                suppression = SuppressionEntry(
                    tenant_id=subscriber.tenant_id,
                    email=email,
                    reason="bounce",
                    source=payload.get("campaign_id", "webhook"),
                )
                db.add(suppression)

            # Update subscriber status
            subscriber.status = "bounced"

        db.commit()


@celery_app.task(queue="track")
def process_complaint(payload: dict):
    with SyncSessionFactory() as db:
        email = payload["email"]

        subscriber = db.execute(
            select(Subscriber).where(Subscriber.email == email)
        ).scalar_one_or_none()
        if not subscriber:
            return

        # Add to suppression
        existing = db.execute(
            select(SuppressionEntry).where(
                SuppressionEntry.tenant_id == subscriber.tenant_id,
                SuppressionEntry.email == email,
            )
        ).scalar_one_or_none()
        if not existing:
            suppression = SuppressionEntry(
                tenant_id=subscriber.tenant_id,
                email=email,
                reason="complaint",
                source=payload.get("campaign_id", "webhook"),
            )
            db.add(suppression)

        subscriber.status = "unsubscribed"
        db.commit()


@celery_app.task(queue="track")
def process_unsubscribe(payload: dict):
    with SyncSessionFactory() as db:
        subscriber_id = uuid.UUID(payload["subscriber_id"])
        campaign_id = uuid.UUID(payload["campaign_id"]) if payload.get("campaign_id") else None
        tenant_id = uuid.UUID(payload["tenant_id"]) if payload.get("tenant_id") else None

        subscriber = db.execute(
            select(Subscriber).where(Subscriber.id == subscriber_id)
        ).scalar_one_or_none()
        if not subscriber:
            return

        effective_tenant_id = tenant_id or subscriber.tenant_id

        # Record tracking event — only if campaign belongs to same tenant
        if campaign_id:
            campaign = db.execute(
                select(Campaign).where(
                    Campaign.id == campaign_id,
                    Campaign.tenant_id == subscriber.tenant_id,
                )
            ).scalar_one_or_none()

            if campaign:
                now = datetime.now(timezone.utc)
                fingerprint = f"unsubscribe:{campaign_id}:{subscriber_id}"

                existing = db.execute(
                    select(TrackingEvent.id).where(TrackingEvent.fingerprint == fingerprint)
                ).scalar_one_or_none()
                if not existing:
                    event = TrackingEvent(
                        tenant_id=subscriber.tenant_id,
                        campaign_id=campaign_id,
                        subscriber_id=subscriber_id,
                        event_type="unsubscribe",
                        occurred_at=now,
                        fingerprint=fingerprint,
                        is_first=True,
                    )
                    db.add(event)

                    db.execute(update(Campaign).where(
                        Campaign.id == campaign_id,
                        Campaign.tenant_id == subscriber.tenant_id,
                    ).values(unsubscribed_count=Campaign.unsubscribed_count + 1))

        # Add to suppression list
        existing_suppression = db.execute(
            select(SuppressionEntry).where(
                SuppressionEntry.tenant_id == effective_tenant_id,
                SuppressionEntry.email == subscriber.email,
            )
        ).scalar_one_or_none()
        if not existing_suppression:
            suppression = SuppressionEntry(
                tenant_id=effective_tenant_id,
                email=subscriber.email,
                reason="unsubscribe",
                source=str(campaign_id) if campaign_id else "manual",
            )
            db.add(suppression)

        # Update subscriber status
        subscriber.status = "unsubscribed"
        db.commit()
