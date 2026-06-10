from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AppException
from app.models.segment import SegmentRule
from app.models.subscriber import Subscriber


class SegmentService:
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def create(self, data: dict) -> SegmentRule:
        if "conditions" in data and not isinstance(data["conditions"][0], dict):
            data["conditions"] = [c.model_dump() if hasattr(c, "model_dump") else c for c in data["conditions"]]
        segment = SegmentRule(tenant_id=self.tenant_id, **data)
        self.db.add(segment)
        await self.db.commit()
        await self.db.refresh(segment)
        return segment

    async def get(self, segment_id: uuid.UUID) -> SegmentRule:
        stmt = select(SegmentRule).where(
            SegmentRule.id == segment_id,
            SegmentRule.tenant_id == self.tenant_id,
            SegmentRule.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        segment = result.scalar_one_or_none()
        if not segment:
            raise AppException(status_code=404, detail="Segment not found")
        return segment

    async def list(self) -> list[SegmentRule]:
        stmt = select(SegmentRule).where(
            SegmentRule.tenant_id == self.tenant_id,
            SegmentRule.deleted_at.is_(None),
        ).order_by(SegmentRule.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, segment_id: uuid.UUID, data: dict) -> SegmentRule:
        segment = await self.get(segment_id)
        if "conditions" in data and data["conditions"] is not None:
            data["conditions"] = [c.model_dump() if hasattr(c, "model_dump") else c for c in data["conditions"]]
        for key, value in data.items():
            if value is not None:
                setattr(segment, key, value)
        await self.db.commit()
        await self.db.refresh(segment)
        return segment

    async def delete(self, segment_id: uuid.UUID) -> None:
        segment = await self.get(segment_id)
        segment.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()

    async def evaluate(self, segment_id: uuid.UUID) -> dict:
        segment = await self.get(segment_id)
        query = self._build_query(segment.conditions)
        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        sample_stmt = query.limit(10)
        result = await self.db.execute(sample_stmt)
        samples = [row.email for row in result.scalars().all()]

        segment.estimated_count = total
        segment.last_evaluated = datetime.now(timezone.utc)
        await self.db.commit()

        return {"segment_id": segment.id, "estimated_count": total, "sample_emails": samples}

    async def get_matching_subscriber_ids(self, segment_id: uuid.UUID) -> list[uuid.UUID]:
        segment = await self.get(segment_id)
        query = self._build_query(segment.conditions)
        stmt = select(Subscriber.id).select_from(query.subquery().alias("sub")).join(
            Subscriber, Subscriber.id == text("sub.id")
        )
        result = await self.db.execute(select(Subscriber.id).where(
            Subscriber.tenant_id == self.tenant_id,
            Subscriber.deleted_at.is_(None),
            Subscriber.status == "confirmed",
            *self._build_conditions(segment.conditions),
        ))
        return [row[0] for row in result.all()]

    def _build_query(self, conditions: list[dict]):
        base = select(Subscriber).where(
            Subscriber.tenant_id == self.tenant_id,
            Subscriber.deleted_at.is_(None),
            Subscriber.status == "confirmed",
        )
        filters = self._build_conditions(conditions)
        if filters:
            base = base.where(*filters)
        return base

    def _build_conditions(self, conditions: list[dict]) -> list:
        filters = []
        for cond in conditions:
            field = cond["field"]
            operator = cond["operator"]
            value = cond["value"]
            clause = self._build_single_condition(field, operator, value)
            if clause is not None:
                filters.append(clause)
        return filters

    def _build_single_condition(self, field: str, operator: str, value: Any):
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
