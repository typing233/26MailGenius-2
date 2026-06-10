from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.schemas.segment import SegmentCreate, SegmentEvaluateResponse, SegmentResponse, SegmentUpdate
from app.services.segment_service import SegmentService

router = APIRouter(prefix="/segments", tags=["segments"])


def _get_service(db: AsyncSession, user: CurrentUser) -> SegmentService:
    return SegmentService(db, user.tenant_id)


@router.post("/", response_model=SegmentResponse, status_code=201)
async def create_segment(
    data: SegmentCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SEGMENT_WRITE),
):
    svc = _get_service(db, user)
    return await svc.create(data.model_dump())


@router.get("/", response_model=list[SegmentResponse])
async def list_segments(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SEGMENT_READ),
):
    svc = _get_service(db, user)
    return await svc.list()


@router.get("/{segment_id}", response_model=SegmentResponse)
async def get_segment(
    segment_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SEGMENT_READ),
):
    svc = _get_service(db, user)
    return await svc.get(segment_id)


@router.put("/{segment_id}", response_model=SegmentResponse)
async def update_segment(
    segment_id: str,
    data: SegmentUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SEGMENT_WRITE),
):
    svc = _get_service(db, user)
    return await svc.update(segment_id, data.model_dump(exclude_unset=True))


@router.delete("/{segment_id}", status_code=204)
async def delete_segment(
    segment_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SEGMENT_WRITE),
):
    svc = _get_service(db, user)
    await svc.delete(segment_id)


@router.post("/{segment_id}/evaluate", response_model=SegmentEvaluateResponse)
async def evaluate_segment(
    segment_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.SEGMENT_READ),
):
    svc = _get_service(db, user)
    return await svc.evaluate(segment_id)
