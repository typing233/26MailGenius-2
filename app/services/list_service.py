import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_filter import TenantQuery
from app.models.mailing_list import ListSubscriber, MailingList
from app.models.subscriber import Subscriber
from app.schemas.mailing_list import BulkOperationResult, MailingListCreate, MailingListUpdate
from app.services.audit_service import AuditService


class ListService:
    def __init__(self, session: AsyncSession, tq: TenantQuery, audit: AuditService):
        self.session = session
        self.tq = tq
        self.audit = audit

    async def list_all(self) -> list[MailingList]:
        stmt = self.tq.query(MailingList).order_by(MailingList.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, list_id: uuid.UUID) -> MailingList:
        return await self.tq.get_or_404(MailingList, list_id)

    async def create(self, data: MailingListCreate) -> MailingList:
        mailing_list = MailingList(
            tenant_id=self.tq.tenant_id,
            name=data.name,
            description=data.description,
            list_type=data.list_type,
        )
        self.session.add(mailing_list)
        await self.session.flush()
        await self.audit.log("create", "mailing_list", mailing_list.id, changes={"name": data.name})
        await self.session.commit()
        return mailing_list

    async def update(self, list_id: uuid.UUID, data: MailingListUpdate) -> MailingList:
        mailing_list = await self.tq.get_or_404(MailingList, list_id)
        changes = {}

        if data.name is not None:
            changes["name"] = {"before": mailing_list.name, "after": data.name}
            mailing_list.name = data.name
        if data.description is not None:
            changes["description"] = {"before": mailing_list.description, "after": data.description}
            mailing_list.description = data.description
        if data.list_type is not None:
            mailing_list.list_type = data.list_type

        mailing_list.updated_at = datetime.now(timezone.utc)
        mailing_list.version += 1
        await self.audit.log("update", "mailing_list", list_id, changes=changes)
        await self.session.commit()
        return mailing_list

    async def delete(self, list_id: uuid.UUID) -> None:
        mailing_list = await self.tq.get_or_404(MailingList, list_id)
        mailing_list.deleted_at = datetime.now(timezone.utc)
        await self.audit.log("soft_delete", "mailing_list", list_id)
        await self.session.commit()

    async def add_subscribers(
        self, list_id: uuid.UUID, subscriber_ids: list[uuid.UUID], expected_version: int | None = None
    ) -> BulkOperationResult:
        mailing_list = await self.tq.get_or_404(MailingList, list_id)

        if expected_version is not None and mailing_list.version != expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Concurrent modification detected. Expected version {expected_version}, current is {mailing_list.version}",
            )

        # Lock the list row for the duration
        stmt = select(MailingList).where(MailingList.id == list_id).with_for_update()
        await self.session.execute(stmt)

        success_count = 0
        errors = []

        for sub_id in subscriber_ids:
            subscriber = await self.tq.get(Subscriber, sub_id)
            if subscriber is None:
                errors.append({"subscriber_id": str(sub_id), "error": "not found"})
                continue

            existing = await self._get_active_association(list_id, sub_id)
            if existing:
                errors.append({"subscriber_id": str(sub_id), "error": "already in list"})
                continue

            assoc = ListSubscriber(
                tenant_id=self.tq.tenant_id,
                list_id=list_id,
                subscriber_id=sub_id,
            )
            self.session.add(assoc)
            success_count += 1

            await self.audit.log(
                "add_to_list", "list_subscriber", assoc.id,
                changes={"list_id": str(list_id), "subscriber_id": str(sub_id)},
            )

        mailing_list.version += 1
        await self.session.commit()

        return BulkOperationResult(success_count=success_count, error_count=len(errors), errors=errors)

    async def remove_subscribers(self, list_id: uuid.UUID, subscriber_ids: list[uuid.UUID]) -> BulkOperationResult:
        await self.tq.get_or_404(MailingList, list_id)

        success_count = 0
        errors = []

        for sub_id in subscriber_ids:
            assoc = await self._get_active_association(list_id, sub_id)
            if assoc is None:
                errors.append({"subscriber_id": str(sub_id), "error": "not in list"})
                continue

            assoc.unsubscribed_at = datetime.now(timezone.utc)
            success_count += 1

            await self.audit.log(
                "remove_from_list", "list_subscriber", assoc.id,
                changes={"list_id": str(list_id), "subscriber_id": str(sub_id)},
            )

        await self.session.commit()
        return BulkOperationResult(success_count=success_count, error_count=len(errors), errors=errors)

    async def get_list_subscribers(self, list_id: uuid.UUID) -> list[Subscriber]:
        await self.tq.get_or_404(MailingList, list_id)
        stmt = (
            select(Subscriber)
            .join(ListSubscriber, ListSubscriber.subscriber_id == Subscriber.id)
            .where(
                ListSubscriber.list_id == list_id,
                ListSubscriber.tenant_id == self.tq.tenant_id,
                ListSubscriber.unsubscribed_at.is_(None),
                Subscriber.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_active_association(self, list_id: uuid.UUID, subscriber_id: uuid.UUID) -> ListSubscriber | None:
        stmt = select(ListSubscriber).where(
            ListSubscriber.list_id == list_id,
            ListSubscriber.subscriber_id == subscriber_id,
            ListSubscriber.tenant_id == self.tq.tenant_id,
            ListSubscriber.unsubscribed_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
