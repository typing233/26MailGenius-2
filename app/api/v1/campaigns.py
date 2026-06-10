from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.schemas.campaign import (
    CampaignCreate,
    CampaignProgressResponse,
    CampaignResponse,
    CampaignStatsResponse,
    CampaignUpdate,
    ScheduleRequest,
    TestSendRequest,
)
from app.services.campaign_service import CampaignService

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _get_service(db: AsyncSession, user: CurrentUser) -> CampaignService:
    return CampaignService(db, user.tenant_id)


@router.post("/", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_WRITE),
):
    svc = _get_service(db, user)
    return await svc.create(data.model_dump(), user_id=user.id)


@router.get("/", response_model=dict)
async def list_campaigns(
    status: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_READ),
):
    svc = _get_service(db, user)
    campaigns, total = await svc.list(status=status, offset=offset, limit=limit)
    return {"items": [CampaignResponse.model_validate(c) for c in campaigns], "total": total}


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_READ),
):
    svc = _get_service(db, user)
    return await svc.get(campaign_id)


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_WRITE),
):
    svc = _get_service(db, user)
    return await svc.update(campaign_id, data.model_dump(exclude_unset=True))


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_WRITE),
):
    svc = _get_service(db, user)
    await svc.delete(campaign_id)


@router.post("/{campaign_id}/schedule", response_model=CampaignResponse)
async def schedule_campaign(
    campaign_id: str,
    data: ScheduleRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_WRITE),
):
    svc = _get_service(db, user)
    return await svc.schedule(campaign_id, data.scheduled_at, data.timezone)


@router.post("/{campaign_id}/send-now", response_model=CampaignResponse)
async def send_now(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_WRITE),
):
    svc = _get_service(db, user)
    return await svc.send_now(campaign_id)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_WRITE),
):
    svc = _get_service(db, user)
    return await svc.pause(campaign_id)


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_WRITE),
):
    svc = _get_service(db, user)
    return await svc.resume(campaign_id)


@router.post("/{campaign_id}/cancel", response_model=CampaignResponse)
async def cancel_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_WRITE),
):
    svc = _get_service(db, user)
    return await svc.cancel(campaign_id)


@router.post("/{campaign_id}/test-send")
async def test_send(
    campaign_id: str,
    data: TestSendRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_WRITE),
):
    from app.worker.tasks.send_tasks import send_test_email
    send_test_email.delay(str(campaign_id), data.to_emails, data.variables)
    return {"message": "Test emails queued", "to": data.to_emails}


@router.get("/{campaign_id}/progress", response_model=CampaignProgressResponse)
async def get_progress(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_READ),
):
    svc = _get_service(db, user)
    return await svc.get_progress(campaign_id)


@router.get("/{campaign_id}/stats", response_model=CampaignStatsResponse)
async def get_stats(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_READ),
):
    svc = _get_service(db, user)
    return await svc.get_stats(campaign_id)


@router.get("/{campaign_id}/errors")
async def get_errors(
    campaign_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_READ),
):
    svc = _get_service(db, user)
    errors, total = await svc.get_errors(campaign_id, offset=offset, limit=limit)
    return {"items": errors, "total": total}


@router.post("/{campaign_id}/errors/{job_id}/retry")
async def retry_error(
    campaign_id: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CAMPAIGN_WRITE),
):
    from app.worker.tasks.send_tasks import retry_failed_job
    retry_failed_job.delay(job_id)
    return {"message": "Retry queued", "job_id": job_id}
