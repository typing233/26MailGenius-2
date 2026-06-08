import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser, get_current_user
from app.schemas.subscriber import SubscriberResponse
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
        return {"message": "Thank you for subscribing!"}  # Silent rejection

    audit = AuditService(db, tenant_id, user_id=None, ip_address=request.client.host if request.client else None)
    service = SubscriptionService(db, tenant_id, audit)

    try:
        token = await service.initiate_subscribe(email, source="form")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # In production, send confirmation email with token. Here we return token for testing.
    return {"message": "Confirmation email sent", "confirmation_token": token}


@router.post("/confirm/{token}")
async def confirm_subscription(token: str, db: AsyncSession = Depends(get_db)):
    # We need to find the tenant from the token — tokens are globally unique by hash
    from app.models.confirmation import ConfirmationToken
    from sqlalchemy import select
    import hashlib

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
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    audit = AuditService(db, current_user.tenant_id, current_user.id)
    service = SubscriptionService(db, current_user.tenant_id, audit)

    try:
        token = await service.initiate_unsubscribe(subscriber_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Unsubscribe confirmation sent", "confirmation_token": token}
