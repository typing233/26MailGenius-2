import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.core.tenant_filter import TenantQuery
from app.database import get_db
from app.dependencies import CurrentUser, get_current_user, require_permissions
from app.schemas.subscriber import (
    PaginatedResponse,
    PaginationParams,
    SubscriberCreate,
    SubscriberFilter,
    SubscriberMergeRequest,
    SubscriberResponse,
    SubscriberUpdate,
)
from app.services.audit_service import AuditService
from app.services.subscriber_service import SubscriberService

router = APIRouter(prefix="/subscribers", tags=["subscribers"])


def _get_service(db: AsyncSession, user: CurrentUser) -> SubscriberService:
    tq = TenantQuery(db, user.tenant_id)
    audit = AuditService(db, user.tenant_id, user.id)
    return SubscriberService(db, tq, audit)


@router.get("", response_model=PaginatedResponse)
async def list_subscribers(
    email: str | None = None,
    status: str | None = None,
    name: str | None = None,
    tags: list[str] | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SUBSCRIBER_READ),
):
    service = _get_service(db, current_user)
    filters = SubscriberFilter(email=email, status=status, name=name, tags=tags)
    pagination = PaginationParams(offset=offset, limit=limit)
    return await service.list_subscribers(filters, pagination)


@router.get("/{subscriber_id}", response_model=SubscriberResponse)
async def get_subscriber(
    subscriber_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SUBSCRIBER_READ),
):
    service = _get_service(db, current_user)
    return await service.get_subscriber(subscriber_id)


@router.post("", response_model=SubscriberResponse, status_code=201)
async def create_subscriber(
    data: SubscriberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SUBSCRIBER_WRITE),
):
    service = _get_service(db, current_user)
    return await service.create_subscriber(data)


@router.patch("/{subscriber_id}", response_model=SubscriberResponse)
async def update_subscriber(
    subscriber_id: uuid.UUID,
    data: SubscriberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SUBSCRIBER_WRITE),
):
    service = _get_service(db, current_user)
    return await service.update_subscriber(subscriber_id, data)


@router.delete("/{subscriber_id}", status_code=204)
async def delete_subscriber(
    subscriber_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SUBSCRIBER_DELETE),
):
    service = _get_service(db, current_user)
    await service.delete_subscriber(subscriber_id)


@router.get("/{email}/duplicates", response_model=list[SubscriberResponse])
async def detect_duplicates(
    email: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SUBSCRIBER_READ),
):
    service = _get_service(db, current_user)
    return await service.detect_duplicates(email)


@router.post("/merge", response_model=SubscriberResponse)
async def merge_subscribers(
    data: SubscriberMergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SUBSCRIBER_WRITE),
):
    service = _get_service(db, current_user)
    return await service.merge_subscribers(data.primary_id, data.duplicate_ids)
