import uuid
from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class TenantQuery:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    def query(self, model):
        stmt = select(model).where(model.tenant_id == self.tenant_id)
        if hasattr(model, "deleted_at"):
            stmt = stmt.where(model.deleted_at.is_(None))
        return stmt

    async def get(self, model, entity_id: uuid.UUID):
        stmt = self.query(model).where(model.id == entity_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_404(self, model, entity_id: uuid.UUID):
        entity = await self.get(model, entity_id)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        return entity

    async def count(self, stmt) -> int:
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await self.session.execute(count_stmt)
        return result.scalar_one()

    async def exists(self, model, **filters) -> bool:
        stmt = self.query(model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(model, key) == value)
        stmt = select(func.count()).select_from(stmt.subquery())
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0
