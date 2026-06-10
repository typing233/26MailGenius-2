from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.models.dead_letter import DeadLetterJob
from app.models.campaign import CampaignJob

router = APIRouter(prefix="/dead-letter", tags=["dead-letter"])


@router.get("/")
async def list_dead_letter(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SEND_QUEUE_READ),
):
    base = select(DeadLetterJob).where(
        DeadLetterJob.tenant_id == user.tenant_id,
        DeadLetterJob.resolved_at.is_(None),
    )
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = base.order_by(DeadLetterJob.moved_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": items, "total": total}


@router.get("/{dlj_id}")
async def get_dead_letter(
    dlj_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SEND_QUEUE_READ),
):
    import uuid
    stmt = select(DeadLetterJob).where(
        DeadLetterJob.id == uuid.UUID(dlj_id),
        DeadLetterJob.tenant_id == user.tenant_id,
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        from app.exceptions import AppException
        raise AppException(status_code=404, detail="Dead letter job not found")
    return item


@router.post("/{dlj_id}/retry")
async def retry_dead_letter(
    dlj_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SEND_QUEUE_WRITE),
):
    import uuid
    from datetime import datetime, timezone
    stmt = select(DeadLetterJob).where(
        DeadLetterJob.id == uuid.UUID(dlj_id),
        DeadLetterJob.tenant_id == user.tenant_id,
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        from app.exceptions import AppException
        raise AppException(status_code=404, detail="Dead letter job not found")

    item.resolved_at = datetime.now(timezone.utc)
    item.resolution = "manual_retry"
    await db.commit()

    from app.worker.tasks.send_tasks import retry_failed_job
    retry_failed_job.delay(str(item.campaign_job_id))
    return {"message": "Retry queued"}


@router.post("/{dlj_id}/skip")
async def skip_dead_letter(
    dlj_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SEND_QUEUE_WRITE),
):
    import uuid
    from datetime import datetime, timezone
    stmt = select(DeadLetterJob).where(
        DeadLetterJob.id == uuid.UUID(dlj_id),
        DeadLetterJob.tenant_id == user.tenant_id,
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        from app.exceptions import AppException
        raise AppException(status_code=404, detail="Dead letter job not found")

    item.resolved_at = datetime.now(timezone.utc)
    item.resolution = "skipped"
    await db.commit()
    return {"message": "Marked as skipped"}


@router.post("/batch-retry")
async def batch_retry(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SEND_QUEUE_WRITE),
):
    from datetime import datetime, timezone
    stmt = select(DeadLetterJob).where(
        DeadLetterJob.tenant_id == user.tenant_id,
        DeadLetterJob.resolved_at.is_(None),
    ).limit(100)
    result = await db.execute(stmt)
    items = result.scalars().all()

    from app.worker.tasks.send_tasks import retry_failed_job
    count = 0
    for item in items:
        item.resolved_at = datetime.now(timezone.utc)
        item.resolution = "manual_retry"
        retry_failed_job.delay(str(item.campaign_job_id))
        count += 1
    await db.commit()
    return {"message": f"{count} jobs queued for retry"}
