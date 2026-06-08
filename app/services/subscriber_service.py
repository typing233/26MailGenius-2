import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_filter import TenantQuery
from app.models.mailing_list import ListSubscriber
from app.models.subscriber import Subscriber
from app.schemas.subscriber import (
    PaginatedResponse,
    PaginationParams,
    SubscriberCreate,
    SubscriberFilter,
    SubscriberUpdate,
)
from app.services.audit_service import AuditService


class SubscriberService:
    def __init__(self, session: AsyncSession, tq: TenantQuery, audit: AuditService):
        self.session = session
        self.tq = tq
        self.audit = audit

    async def list_subscribers(self, filters: SubscriberFilter, pagination: PaginationParams) -> PaginatedResponse:
        stmt = self.tq.query(Subscriber)

        if filters.email:
            stmt = stmt.where(Subscriber.email.ilike(f"%{filters.email}%"))
        if filters.status:
            stmt = stmt.where(Subscriber.status == filters.status)
        if filters.name:
            stmt = stmt.where(Subscriber.name.ilike(f"%{filters.name}%"))
        if filters.tags:
            stmt = stmt.where(Subscriber.tags.contains(filters.tags))

        total = await self.tq.count(stmt)
        stmt = stmt.order_by(Subscriber.created_at.desc())
        stmt = stmt.offset(pagination.offset).limit(pagination.limit)

        result = await self.session.execute(stmt)
        items = result.scalars().all()

        return PaginatedResponse(items=items, total=total, offset=pagination.offset, limit=pagination.limit)

    async def get_subscriber(self, subscriber_id: uuid.UUID) -> Subscriber:
        return await self.tq.get_or_404(Subscriber, subscriber_id)

    async def create_subscriber(self, data: SubscriberCreate) -> Subscriber:
        existing = await self._find_by_email(data.email)
        if existing:
            raise ValueError(f"Subscriber with email {data.email} already exists")

        subscriber = Subscriber(
            tenant_id=self.tq.tenant_id,
            email=data.email,
            name=data.name,
            status="pending",
            custom_fields=data.custom_fields,
            tags=data.tags,
            source=data.source or "api",
        )
        self.session.add(subscriber)
        await self.session.flush()

        await self.audit.log("create", "subscriber", subscriber.id, changes={"email": data.email})
        await self.session.commit()
        return subscriber

    async def update_subscriber(self, subscriber_id: uuid.UUID, data: SubscriberUpdate) -> Subscriber:
        subscriber = await self.tq.get_or_404(Subscriber, subscriber_id)
        changes = {}

        if data.name is not None:
            changes["name"] = {"before": subscriber.name, "after": data.name}
            subscriber.name = data.name
        if data.custom_fields is not None:
            changes["custom_fields"] = {"before": subscriber.custom_fields, "after": data.custom_fields}
            subscriber.custom_fields = data.custom_fields
        if data.tags is not None:
            changes["tags"] = {"before": subscriber.tags, "after": data.tags}
            subscriber.tags = data.tags

        subscriber.updated_at = datetime.now(timezone.utc)
        subscriber.version += 1

        await self.audit.log("update", "subscriber", subscriber.id, changes=changes)
        await self.session.commit()
        return subscriber

    async def delete_subscriber(self, subscriber_id: uuid.UUID) -> None:
        subscriber = await self.tq.get_or_404(Subscriber, subscriber_id)
        subscriber.deleted_at = datetime.now(timezone.utc)
        await self.audit.log("soft_delete", "subscriber", subscriber.id)
        await self.session.commit()

    async def detect_duplicates(self, email: str) -> list[Subscriber]:
        stmt = self.tq.query(Subscriber).where(func.lower(Subscriber.email) == email.lower())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def merge_subscribers(self, primary_id: uuid.UUID, duplicate_ids: list[uuid.UUID]) -> Subscriber:
        primary = await self.tq.get_or_404(Subscriber, primary_id)

        for dup_id in duplicate_ids:
            dup = await self.tq.get_or_404(Subscriber, dup_id)

            # Move list associations
            stmt = select(ListSubscriber).where(
                ListSubscriber.subscriber_id == dup_id,
                ListSubscriber.tenant_id == self.tq.tenant_id,
            )
            result = await self.session.execute(stmt)
            for assoc in result.scalars().all():
                existing = await self._has_list_assoc(primary_id, assoc.list_id)
                if not existing:
                    assoc.subscriber_id = primary_id
                else:
                    await self.session.delete(assoc)

            # Merge custom fields (primary takes precedence)
            merged_fields = {**dup.custom_fields, **primary.custom_fields}
            primary.custom_fields = merged_fields

            # Merge tags
            merged_tags = list(set(primary.tags + dup.tags))
            primary.tags = merged_tags

            # Soft delete duplicate
            dup.deleted_at = datetime.now(timezone.utc)

            await self.audit.log("merge_duplicate", "subscriber", dup_id, changes={"merged_into": str(primary_id)})

        primary.version += 1
        await self.audit.log("merge_primary", "subscriber", primary_id, changes={"absorbed": [str(d) for d in duplicate_ids]})
        await self.session.commit()
        return primary

    async def _find_by_email(self, email: str) -> Subscriber | None:
        stmt = self.tq.query(Subscriber).where(func.lower(Subscriber.email) == email.lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _has_list_assoc(self, subscriber_id: uuid.UUID, list_id: uuid.UUID) -> bool:
        stmt = select(ListSubscriber).where(
            ListSubscriber.subscriber_id == subscriber_id,
            ListSubscriber.list_id == list_id,
            ListSubscriber.tenant_id == self.tq.tenant_id,
            ListSubscriber.unsubscribed_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
