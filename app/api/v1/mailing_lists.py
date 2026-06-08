import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.core.tenant_filter import TenantQuery
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.schemas.mailing_list import (
    BulkOperationResult,
    ListSubscriberAdd,
    ListSubscriberRemove,
    MailingListCreate,
    MailingListResponse,
    MailingListUpdate,
)
from app.schemas.subscriber import SubscriberResponse
from app.services.audit_service import AuditService
from app.services.list_service import ListService

router = APIRouter(prefix="/lists", tags=["mailing_lists"])


def _get_service(db: AsyncSession, user: CurrentUser) -> ListService:
    tq = TenantQuery(db, user.tenant_id)
    audit = AuditService(db, user.tenant_id, user.id)
    return ListService(db, tq, audit)


@router.get("", response_model=list[MailingListResponse])
async def list_all(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.LIST_READ),
):
    service = _get_service(db, current_user)
    return await service.list_all()


@router.get("/{list_id}", response_model=MailingListResponse)
async def get_list(
    list_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.LIST_READ),
):
    service = _get_service(db, current_user)
    return await service.get(list_id)


@router.post("", response_model=MailingListResponse, status_code=201)
async def create_list(
    data: MailingListCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.LIST_WRITE),
):
    service = _get_service(db, current_user)
    return await service.create(data)


@router.patch("/{list_id}", response_model=MailingListResponse)
async def update_list(
    list_id: uuid.UUID,
    data: MailingListUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.LIST_WRITE),
):
    service = _get_service(db, current_user)
    return await service.update(list_id, data)


@router.delete("/{list_id}", status_code=204)
async def delete_list(
    list_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.LIST_DELETE),
):
    service = _get_service(db, current_user)
    await service.delete(list_id)


@router.post("/{list_id}/subscribers", response_model=BulkOperationResult)
async def add_subscribers_to_list(
    list_id: uuid.UUID,
    data: ListSubscriberAdd,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.LIST_WRITE),
):
    service = _get_service(db, current_user)
    return await service.add_subscribers(list_id, data.subscriber_ids, data.expected_version)


@router.delete("/{list_id}/subscribers", response_model=BulkOperationResult)
async def remove_subscribers_from_list(
    list_id: uuid.UUID,
    data: ListSubscriberRemove,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.LIST_WRITE),
):
    service = _get_service(db, current_user)
    return await service.remove_subscribers(list_id, data.subscriber_ids)


@router.get("/{list_id}/subscribers", response_model=list[SubscriberResponse])
async def get_list_subscribers(
    list_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.LIST_READ),
):
    service = _get_service(db, current_user)
    return await service.get_list_subscribers(list_id)
