import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.core.tenant_filter import TenantQuery
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.schemas.send_queue import SendQueueJobCreate, SendQueueJobResponse
from app.services.send_queue_service import SendQueueService

router = APIRouter(prefix="/send-queue", tags=["send_queue"])


def _get_service(db: AsyncSession, user: CurrentUser) -> SendQueueService:
    tq = TenantQuery(db, user.tenant_id)
    return SendQueueService(db, tq)


@router.post("", response_model=SendQueueJobResponse, status_code=201)
async def enqueue_job(
    data: SendQueueJobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SEND_QUEUE_WRITE),
):
    service = _get_service(db, current_user)
    return await service.enqueue(data)


@router.get("/{job_id}", response_model=SendQueueJobResponse)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SEND_QUEUE_READ),
):
    service = _get_service(db, current_user)
    return await service.get_job(job_id)


@router.post("/{job_id}/cancel", response_model=SendQueueJobResponse)
async def cancel_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SEND_QUEUE_WRITE),
):
    service = _get_service(db, current_user)
    return await service.cancel_job(job_id)


@router.get("", response_model=list[SendQueueJobResponse])
async def list_pending_jobs(
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SEND_QUEUE_READ),
):
    service = _get_service(db, current_user)
    return await service.get_pending_jobs(limit)
