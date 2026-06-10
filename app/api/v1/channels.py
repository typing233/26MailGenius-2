from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.schemas.channel import (
    ChannelCreate,
    ChannelHealthResponse,
    ChannelResponse,
    ChannelTestRequest,
    ChannelUpdate,
)
from app.services.channel_service import ChannelService

router = APIRouter(prefix="/channels", tags=["channels"])


def _get_service(db: AsyncSession, user: CurrentUser) -> ChannelService:
    return ChannelService(db, user.tenant_id)


@router.post("/", response_model=ChannelResponse, status_code=201)
async def create_channel(
    data: ChannelCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CHANNEL_WRITE),
):
    svc = _get_service(db, user)
    return await svc.create(data.model_dump())


@router.get("/", response_model=list[ChannelResponse])
async def list_channels(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CHANNEL_READ),
):
    svc = _get_service(db, user)
    return await svc.list()


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CHANNEL_READ),
):
    svc = _get_service(db, user)
    return await svc.get(channel_id)


@router.put("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    data: ChannelUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CHANNEL_WRITE),
):
    svc = _get_service(db, user)
    return await svc.update(channel_id, data.model_dump(exclude_unset=True))


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CHANNEL_WRITE),
):
    svc = _get_service(db, user)
    await svc.delete(channel_id)


@router.post("/{channel_id}/test")
async def test_channel(
    channel_id: str,
    data: ChannelTestRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CHANNEL_WRITE),
):
    svc = _get_service(db, user)
    return await svc.test_connection(channel_id, data.to_email)


@router.get("/{channel_id}/health", response_model=ChannelHealthResponse)
async def get_health(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.CHANNEL_READ),
):
    svc = _get_service(db, user)
    return await svc.get_health(channel_id)
