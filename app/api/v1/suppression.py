import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.models.suppression import SuppressionEntry

router = APIRouter(prefix="/suppression", tags=["suppression"])


@router.get("/")
async def list_suppression(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SUBSCRIBER_READ),
):
    base = select(SuppressionEntry).where(SuppressionEntry.tenant_id == user.tenant_id)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = base.order_by(SuppressionEntry.suppressed_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return {"items": result.scalars().all(), "total": total}


@router.post("/", status_code=201)
async def add_suppression(
    email: str = Query(...),
    reason: str = Query(default="manual"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SUBSCRIBER_WRITE),
):
    existing = await db.execute(
        select(SuppressionEntry).where(
            SuppressionEntry.tenant_id == user.tenant_id,
            SuppressionEntry.email == email,
        )
    )
    if existing.scalar_one_or_none():
        from app.exceptions import AppException
        raise AppException(status_code=409, detail="Email already suppressed")

    entry = SuppressionEntry(
        tenant_id=user.tenant_id,
        email=email,
        reason=reason,
        source="manual",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
async def remove_suppression(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SUBSCRIBER_WRITE),
):
    stmt = select(SuppressionEntry).where(
        SuppressionEntry.id == uuid.UUID(entry_id),
        SuppressionEntry.tenant_id == user.tenant_id,
    )
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()
    if not entry:
        from app.exceptions import AppException
        raise AppException(status_code=404, detail="Entry not found")
    await db.delete(entry)
    await db.commit()
