import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_filter import TenantQuery
from app.models.send_queue import SendQueueJob
from app.schemas.send_queue import SendQueueJobCreate


class SendQueueInterface(ABC):
    @abstractmethod
    async def enqueue(self, data: SendQueueJobCreate) -> SendQueueJob:
        ...

    @abstractmethod
    async def get_job(self, job_id: uuid.UUID) -> SendQueueJob:
        ...

    @abstractmethod
    async def cancel_job(self, job_id: uuid.UUID) -> SendQueueJob:
        ...

    @abstractmethod
    async def get_pending_jobs(self, limit: int = 100) -> list[SendQueueJob]:
        ...


class SendQueueService(SendQueueInterface):
    def __init__(self, session: AsyncSession, tq: TenantQuery):
        self.session = session
        self.tq = tq

    async def enqueue(self, data: SendQueueJobCreate) -> SendQueueJob:
        # Validate subscriber belongs to this tenant
        from app.models.subscriber import Subscriber
        subscriber = await self.tq.get(Subscriber, data.subscriber_id)
        if subscriber is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subscriber not found in this tenant")

        # Validate list belongs to this tenant if provided
        if data.list_id is not None:
            from app.models.mailing_list import MailingList
            ml = await self.tq.get(MailingList, data.list_id)
            if ml is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mailing list not found in this tenant")

        job = SendQueueJob(
            tenant_id=self.tq.tenant_id,
            campaign_id=data.campaign_id,
            subscriber_id=data.subscriber_id,
            list_id=data.list_id,
            status="queued",
            scheduled_at=data.scheduled_at,
        )
        self.session.add(job)
        await self.session.commit()
        return job

    async def get_job(self, job_id: uuid.UUID) -> SendQueueJob:
        return await self.tq.get_or_404(SendQueueJob, job_id)

    async def cancel_job(self, job_id: uuid.UUID) -> SendQueueJob:
        job = await self.tq.get_or_404(SendQueueJob, job_id)
        if job.status != "queued":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Can only cancel queued jobs")
        job.status = "cancelled"
        await self.session.commit()
        return job

    async def get_pending_jobs(self, limit: int = 100) -> list[SendQueueJob]:
        stmt = (
            self.tq.query(SendQueueJob)
            .where(SendQueueJob.status == "queued")
            .order_by(SendQueueJob.scheduled_at.asc().nullsfirst())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
