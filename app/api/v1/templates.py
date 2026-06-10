from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.schemas.template import (
    TemplateCreate,
    TemplateListResponse,
    TemplatePreviewRequest,
    TemplateRenderTestRequest,
    TemplateResponse,
    TemplateUpdate,
    TemplateValidateResponse,
    TemplateVersionResponse,
)
from app.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["templates"])


def _get_service(db: AsyncSession, user: CurrentUser) -> TemplateService:
    return TemplateService(db, user.tenant_id)


@router.post("/", response_model=TemplateResponse, status_code=201)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.TEMPLATE_WRITE),
):
    svc = _get_service(db, user)
    template = await svc.create(data.model_dump(), user_id=user.id)
    return template


@router.get("/", response_model=dict)
async def list_templates(
    category: str | None = None,
    search: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.TEMPLATE_READ),
):
    svc = _get_service(db, user)
    templates, total = await svc.list(category=category, search=search, offset=offset, limit=limit)
    return {"items": [TemplateListResponse.model_validate(t) for t in templates], "total": total}


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.TEMPLATE_READ),
):
    svc = _get_service(db, user)
    return await svc.get(template_id)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.TEMPLATE_WRITE),
):
    svc = _get_service(db, user)
    return await svc.update(template_id, data.model_dump(exclude_unset=True), user_id=user.id)


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.TEMPLATE_WRITE),
):
    svc = _get_service(db, user)
    await svc.delete(template_id)


@router.get("/{template_id}/versions", response_model=list[TemplateVersionResponse])
async def list_versions(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.TEMPLATE_READ),
):
    svc = _get_service(db, user)
    return await svc.get_versions(template_id)


@router.get("/{template_id}/versions/{version}", response_model=TemplateVersionResponse)
async def get_version(
    template_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.TEMPLATE_READ),
):
    svc = _get_service(db, user)
    return await svc.get_version(template_id, version)


@router.post("/{template_id}/versions/{version}/restore", response_model=TemplateResponse)
async def restore_version(
    template_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.TEMPLATE_WRITE),
):
    svc = _get_service(db, user)
    return await svc.restore_version(template_id, version, user_id=user.id)


@router.post("/{template_id}/preview")
async def preview_template(
    template_id: str,
    data: TemplatePreviewRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.TEMPLATE_READ),
):
    svc = _get_service(db, user)
    return await svc.preview(template_id, data.variables)


@router.post("/{template_id}/validate", response_model=TemplateValidateResponse)
async def validate_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.TEMPLATE_READ),
):
    svc = _get_service(db, user)
    return await svc.validate(template_id)


@router.post("/render-test")
async def render_test(
    data: TemplateRenderTestRequest,
    user: CurrentUser = require_permissions(Permission.TEMPLATE_READ),
):
    svc = TemplateService.__new__(TemplateService)
    return svc.render_test(data.html_body, data.variables)
