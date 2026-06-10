import hashlib
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
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
    campaign: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Public one-click unsubscribe endpoint (RFC 8058). No auth required — used from List-Unsubscribe header."""
    from app.models.subscriber import Subscriber

    stmt = select(Subscriber).where(Subscriber.id == subscriber_id)
    result = await db.execute(stmt)
    subscriber = result.scalar_one_or_none()
    if not subscriber:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscriber not found")

    # Mark subscriber as unsubscribed
    subscriber.status = "unsubscribed"
    await db.commit()

    # Trigger tracking + suppression via Celery task
    from app.worker.tasks.tracking_tasks import process_unsubscribe
    process_unsubscribe.delay({
        "subscriber_id": str(subscriber_id),
        "campaign_id": str(campaign) if campaign else None,
        "tenant_id": str(subscriber.tenant_id),
    })

    return {"message": "You have been unsubscribed successfully"}
