import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.core.tenant_filter import TenantQuery
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.models.subscriber import Subscriber
from app.schemas.import_job import ImportJobResponse
from app.services.audit_service import AuditService
from app.services.import_service import ImportService
from app.utils.csv_processor import generate_csv_export_line

router = APIRouter(prefix="/import-export", tags=["import_export"])


def _get_service(db: AsyncSession, user: CurrentUser) -> ImportService:
    tq = TenantQuery(db, user.tenant_id)
    audit = AuditService(db, user.tenant_id, user.id)
    return ImportService(db, tq, audit)


@router.post("/import", response_model=ImportJobResponse, status_code=202)
async def import_subscribers(
    file: UploadFile = File(...),
    dedup_key: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SUBSCRIBER_IMPORT),
):
    content = await file.read()
    service = _get_service(db, current_user)
    job = await service.initiate_import(
        content=content,
        filename=file.filename or "upload.csv",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        dedup_key=dedup_key,
    )
    return job


@router.get("/import/{job_id}", response_model=ImportJobResponse)
async def get_import_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SUBSCRIBER_IMPORT),
):
    service = _get_service(db, current_user)
    return await service.get_job_status(job_id)


@router.get("/export")
async def export_subscribers(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = require_permissions(Permission.SUBSCRIBER_EXPORT),
):
    tq = TenantQuery(db, current_user.tenant_id)

    async def generate() -> AsyncIterator[str]:
        yield "email,name,status,tags\n"
        stmt = tq.query(Subscriber).order_by(Subscriber.created_at.desc())
        result = await db.execute(stmt)
        for subscriber in result.scalars():
            yield generate_csv_export_line(subscriber)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=subscribers_export.csv"},
    )
