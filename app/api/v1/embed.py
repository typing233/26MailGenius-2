import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.core.tenant_filter import TenantQuery
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.schemas.embed_form import EmbedCodeResponse, EmbedFormConfigCreate, EmbedFormConfigResponse
from app.services.audit_service import AuditService
from app.services.embed_service import EmbedService

router = APIRouter(prefix="/embed", tags=["embed"])


def _get_service(db: AsyncSession, user: CurrentUser) -> EmbedService:
    tq = TenantQuery(db, user.tenant_id)
    audit = AuditService(db, user.tenant_id, user.id)
    return EmbedService(db, tq, audit)


@router.post("", response_model=EmbedFormConfigResponse, status_code=201)
async def create_embed_config(
    data: EmbedFormConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.LIST_WRITE),
):
    service = _get_service(db, current_user)
    return await service.create_config(data)


@router.get("/{config_id}", response_model=EmbedFormConfigResponse)
async def get_embed_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.LIST_READ),
):
    service = _get_service(db, current_user)
    return await service.get_config(config_id)


@router.get("/{config_id}/code", response_model=EmbedCodeResponse)
async def get_embed_code(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.LIST_READ),
):
    service = _get_service(db, current_user)
    html = await service.generate_embed_code(config_id)
    return EmbedCodeResponse(html=html, config_id=config_id)
