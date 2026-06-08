import hashlib
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser, get_current_user
from app.models.confirmation import ConfirmationToken
from app.models.tenant import Tenant
from app.services.audit_service import AuditService
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.post("/subscribe")
async def initiate_subscribe(
    email: str = Form(...),
    tenant_id: uuid.UUID = Form(...),
    list_id: uuid.UUID = Form(...),
    name: str | None = Form(None),
    website: str = Form(""),  # honeypot
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    # Anti-abuse: honeypot check
    if website:
        return {"message": "Thank you for subscribing!"}

    # Validate tenant exists
    stmt = select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant")

    audit = AuditService(db, tenant_id, user_id=None, ip_address=request.client.host if request.client else None)
    service = SubscriptionService(db, tenant_id, audit)

    try:
        token = await service.initiate_subscribe(email, source="form", list_id=list_id, name=name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Confirmation email sent", "confirmation_token": token}


@router.post("/confirm/{token}")
async def confirm_subscription(token: str, db: AsyncSession = Depends(get_db)):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = select(ConfirmationToken).where(ConfirmationToken.token_hash == token_hash)
    result = await db.execute(stmt)
    ct = result.scalar_one_or_none()

    if ct is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token")

    audit = AuditService(db, ct.tenant_id, user_id=None)
    service = SubscriptionService(db, ct.tenant_id, audit)

    try:
        subscriber = await service.confirm_token(token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Subscription confirmed", "status": subscriber.status}


@router.post("/unsubscribe/{subscriber_id}")
async def initiate_unsubscribe(
    subscriber_id: uuid.UUID,
    list_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    audit = AuditService(db, current_user.tenant_id, current_user.id)
    service = SubscriptionService(db, current_user.tenant_id, audit)

    try:
        token = await service.initiate_unsubscribe(subscriber_id, list_id=list_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Unsubscribe confirmation sent", "confirmation_token": token}
