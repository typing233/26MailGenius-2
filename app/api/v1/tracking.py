import base64
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.models.campaign import CampaignJob
from app.models.tracking import TrackingEvent, TrackingLink
from app.schemas.tracking import BounceWebhookPayload, ComplaintWebhookPayload, TrackingEventResponse

router = APIRouter(prefix="/tracking", tags=["tracking"])

# 1x1 transparent GIF
PIXEL_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


@router.get("/pixel/{job_id}.gif")
async def tracking_pixel(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Look up job to get campaign/subscriber info
    stmt = select(CampaignJob).where(CampaignJob.id == uuid.UUID(job_id))
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job:
        from app.worker.tasks.tracking_tasks import record_tracking_event
        record_tracking_event.delay({
            "tenant_id": str(job.tenant_id),
            "campaign_id": str(job.campaign_id),
            "subscriber_id": str(job.subscriber_id),
            "job_id": str(job.id),
            "event_type": "open",
            "user_agent": request.headers.get("user-agent", ""),
            "ip_address": request.client.host if request.client else None,
        })

    return Response(
        content=PIXEL_GIF,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/click/{tracking_code}")
async def tracking_click(
    tracking_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TrackingLink).where(TrackingLink.tracking_code == tracking_code)
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()

    if not link:
        return Response(status_code=404, content="Link not found")

    # Validate sid — must be a valid subscriber in this campaign
    sid_raw = request.query_params.get("sid")
    subscriber_id = None
    if sid_raw:
        try:
            sid_uuid = uuid.UUID(sid_raw)
        except ValueError:
            sid_uuid = None

        if sid_uuid:
            from app.models.campaign import CampaignJob
            valid = await db.execute(
                select(CampaignJob.id).where(
                    CampaignJob.campaign_id == link.campaign_id,
                    CampaignJob.subscriber_id == sid_uuid,
                )
            )
            if valid.scalar_one_or_none() is not None:
                subscriber_id = str(sid_uuid)

    if subscriber_id:
        from app.worker.tasks.tracking_tasks import record_tracking_event
        record_tracking_event.delay({
            "tenant_id": str(link.tenant_id),
            "campaign_id": str(link.campaign_id),
            "subscriber_id": subscriber_id,
            "event_type": "click",
            "link_url": link.original_url,
            "user_agent": request.headers.get("user-agent", ""),
            "ip_address": request.client.host if request.client else None,
        })

    return RedirectResponse(
        url=link.original_url,
        status_code=302,
        headers={
            "Cache-Control": "private, max-age=0",
        },
    )


@router.post("/webhook/bounce")
async def bounce_webhook(
    payload: BounceWebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    from app.worker.tasks.tracking_tasks import process_bounce
    data = payload.model_dump()
    data["timestamp"] = data["timestamp"].isoformat() if data.get("timestamp") else None
    process_bounce.delay(data)
    return {"status": "accepted"}


@router.post("/webhook/complaint")
async def complaint_webhook(
    payload: ComplaintWebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    from app.worker.tasks.tracking_tasks import process_complaint
    data = payload.model_dump()
    data["timestamp"] = data["timestamp"].isoformat() if data.get("timestamp") else None
    process_complaint.delay(data)
    return {"status": "accepted"}


@router.get("/events", response_model=dict)
async def list_events(
    campaign_id: str | None = None,
    event_type: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.TRACKING_READ),
):
    from sqlalchemy import func

    base = select(TrackingEvent).where(TrackingEvent.tenant_id == user.tenant_id)
    if campaign_id:
        base = base.where(TrackingEvent.campaign_id == uuid.UUID(campaign_id))
    if event_type:
        base = base.where(TrackingEvent.event_type == event_type)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = base.order_by(TrackingEvent.occurred_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    events = result.scalars().all()
    return {"items": [TrackingEventResponse.model_validate(e) for e in events], "total": total}
