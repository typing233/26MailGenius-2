from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AppException
from app.models.campaign import Campaign, CampaignJob
from app.models.subscriber import Subscriber
from app.models.mailing_list import ListSubscriber


VALID_TRANSITIONS = {
    "draft": {"scheduled", "sending", "cancelled"},
    "scheduled": {"sending", "cancelled", "draft"},
    "sending": {"paused", "completed", "cancelled", "failed"},
    "paused": {"sending", "cancelled"},
}


class CampaignService:
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def create(self, data: dict, user_id: uuid.UUID | None = None) -> Campaign:
        campaign = Campaign(tenant_id=self.tenant_id, created_by=user_id, **data)
        self.db.add(campaign)
        await self.db.commit()
        await self.db.refresh(campaign)
        return campaign

    async def get(self, campaign_id: uuid.UUID) -> Campaign:
        stmt = select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.tenant_id == self.tenant_id,
            Campaign.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise AppException(status_code=404, detail="Campaign not found")
        return campaign

    async def list(
        self, status: str | None = None, offset: int = 0, limit: int = 20
    ) -> tuple[list[Campaign], int]:
        base = select(Campaign).where(
            Campaign.tenant_id == self.tenant_id,
            Campaign.deleted_at.is_(None),
        )
        if status:
            base = base.where(Campaign.status == status)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = base.order_by(Campaign.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def update(self, campaign_id: uuid.UUID, data: dict) -> Campaign:
        campaign = await self.get(campaign_id)
        if campaign.status not in ("draft", "scheduled"):
            raise AppException(status_code=409, detail="Can only edit draft/scheduled campaigns")
        for key, value in data.items():
            if value is not None:
                setattr(campaign, key, value)
        await self.db.commit()
        await self.db.refresh(campaign)
        return campaign

    async def delete(self, campaign_id: uuid.UUID) -> None:
        campaign = await self.get(campaign_id)
        if campaign.status != "draft":
            raise AppException(status_code=409, detail="Can only delete draft campaigns")
        campaign.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()

    async def _transition(self, campaign: Campaign, new_status: str) -> Campaign:
        valid = VALID_TRANSITIONS.get(campaign.status, set())
        if new_status not in valid:
            raise AppException(
                status_code=409,
                detail=f"Cannot transition from '{campaign.status}' to '{new_status}'",
            )
        campaign.status = new_status
        if new_status == "sending":
            campaign.started_at = campaign.started_at or datetime.now(timezone.utc)
            campaign.paused_at = None
        elif new_status == "paused":
            campaign.paused_at = datetime.now(timezone.utc)
        elif new_status == "completed":
            campaign.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(campaign)
        return campaign

    async def schedule(self, campaign_id: uuid.UUID, scheduled_at: datetime, tz: str = "UTC") -> Campaign:
        campaign = await self.get(campaign_id)
        campaign.scheduled_at = scheduled_at
        campaign.timezone = tz
        return await self._transition(campaign, "scheduled")

    async def send_now(self, campaign_id: uuid.UUID) -> Campaign:
        campaign = await self.get(campaign_id)
        campaign = await self._transition(campaign, "sending")
        from app.worker.tasks.campaign_tasks import prepare_campaign
        prepare_campaign.delay(str(campaign.id))
        return campaign

    async def pause(self, campaign_id: uuid.UUID) -> Campaign:
        campaign = await self.get(campaign_id)
        return await self._transition(campaign, "paused")

    async def resume(self, campaign_id: uuid.UUID) -> Campaign:
        campaign = await self.get(campaign_id)
        campaign = await self._transition(campaign, "sending")
        from app.worker.tasks.campaign_tasks import dispatch_batches
        dispatch_batches.delay(str(campaign.id))
        return campaign

    async def cancel(self, campaign_id: uuid.UUID) -> Campaign:
        campaign = await self.get(campaign_id)
        return await self._transition(campaign, "cancelled")

    async def get_progress(self, campaign_id: uuid.UUID) -> dict:
        campaign = await self.get(campaign_id)
        total = campaign.total_recipients or 1
        sent = campaign.sent_count
        failed = campaign.failed_count
        progress_pct = round((sent + failed) / total * 100, 1) if total > 0 else 0
        remaining = None
        if campaign.started_at and sent > 0:
            elapsed = (datetime.now(timezone.utc) - campaign.started_at).total_seconds()
            rate = sent / elapsed if elapsed > 0 else 0
            remaining_count = total - sent - failed
            remaining = int(remaining_count / rate) if rate > 0 else None
        return {
            "campaign_id": campaign.id,
            "status": campaign.status,
            "total_recipients": total,
            "sent_count": sent,
            "failed_count": failed,
            "progress_pct": progress_pct,
            "estimated_remaining_seconds": remaining,
        }

    async def get_stats(self, campaign_id: uuid.UUID) -> dict:
        campaign = await self.get(campaign_id)
        total = campaign.total_recipients or 1
        return {
            "campaign_id": campaign.id,
            "total_recipients": campaign.total_recipients,
            "sent": campaign.sent_count,
            "delivered": campaign.sent_count - campaign.bounced_count,
            "opened": campaign.opened_count,
            "unique_opens": campaign.opened_count,
            "clicked": campaign.clicked_count,
            "unique_clicks": campaign.clicked_count,
            "bounced": campaign.bounced_count,
            "unsubscribed": campaign.unsubscribed_count,
            "open_rate": round(campaign.opened_count / total * 100, 2) if total else 0,
            "click_rate": round(campaign.clicked_count / total * 100, 2) if total else 0,
            "bounce_rate": round(campaign.bounced_count / total * 100, 2) if total else 0,
        }

    async def get_errors(self, campaign_id: uuid.UUID, offset: int = 0, limit: int = 20) -> tuple[list[CampaignJob], int]:
        base = select(CampaignJob).where(
            CampaignJob.campaign_id == campaign_id,
            CampaignJob.tenant_id == self.tenant_id,
            CampaignJob.status.in_(["failed", "dead_letter"]),
        )
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        stmt = base.order_by(CampaignJob.failed_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def resolve_recipients(self, campaign_id: uuid.UUID) -> list[uuid.UUID]:
        campaign = await self.get(campaign_id)
        subscriber_ids: set[uuid.UUID] = set()

        # From lists
        if campaign.list_ids:
            stmt = select(ListSubscriber.subscriber_id).where(
                ListSubscriber.list_id.in_(campaign.list_ids),
                ListSubscriber.unsubscribed_at.is_(None),
            )
            result = await self.db.execute(stmt)
            subscriber_ids.update(row[0] for row in result.all())

        # From segments
        if campaign.segment_rule_ids:
            from app.services.segment_service import SegmentService
            seg_svc = SegmentService(self.db, self.tenant_id)
            for seg_id in campaign.segment_rule_ids:
                ids = await seg_svc.get_matching_subscriber_ids(seg_id)
                subscriber_ids.update(ids)

        # Exclusions
        if campaign.exclusion_list_ids:
            stmt = select(ListSubscriber.subscriber_id).where(
                ListSubscriber.list_id.in_(campaign.exclusion_list_ids),
                ListSubscriber.unsubscribed_at.is_(None),
            )
            result = await self.db.execute(stmt)
            excluded = {row[0] for row in result.all()}
            subscriber_ids -= excluded

        # Suppression list
        from app.models.suppression import SuppressionEntry
        stmt = select(SuppressionEntry.email).where(
            SuppressionEntry.tenant_id == self.tenant_id,
        )
        result = await self.db.execute(stmt)
        suppressed_emails = {row[0] for row in result.all()}

        if suppressed_emails:
            stmt = select(Subscriber.id).where(
                Subscriber.id.in_(list(subscriber_ids)),
                Subscriber.email.in_(suppressed_emails),
            )
            result = await self.db.execute(stmt)
            suppressed_ids = {row[0] for row in result.all()}
            subscriber_ids -= suppressed_ids

        # Only confirmed, non-deleted subscribers
        if subscriber_ids:
            stmt = select(Subscriber.id).where(
                Subscriber.id.in_(list(subscriber_ids)),
                Subscriber.tenant_id == self.tenant_id,
                Subscriber.status == "confirmed",
                Subscriber.deleted_at.is_(None),
            )
            result = await self.db.execute(stmt)
            subscriber_ids = {row[0] for row in result.all()}

        return list(subscriber_ids)
