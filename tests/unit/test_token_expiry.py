import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.confirmation import ConfirmationToken
from app.models.subscriber import Subscriber
from app.models.tenant import Tenant
from app.services.audit_service import AuditService
from app.services.subscription_service import SubscriptionService


@pytest.mark.asyncio
class TestTokenExpiry:
    async def test_expired_token_rejected(self, db_session: AsyncSession, tenant_a: Tenant):
        subscriber = Subscriber(
            id=uuid.uuid4(), tenant_id=tenant_a.id, email="expired@test.com", status="pending",
        )
        db_session.add(subscriber)
        await db_session.flush()

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        ct = ConfirmationToken(
            id=uuid.uuid4(), tenant_id=tenant_a.id, subscriber_id=subscriber.id,
            token_hash=token_hash, action="confirm_subscribe",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # already expired
        )
        db_session.add(ct)
        await db_session.flush()
        await db_session.commit()

        audit = AuditService(db_session, tenant_a.id)
        service = SubscriptionService(db_session, tenant_a.id, audit)

        with pytest.raises(ValueError, match="invalid, expired, or already used"):
            await service.confirm_token(raw_token)

    async def test_consumed_token_rejected(self, db_session: AsyncSession, tenant_a: Tenant):
        subscriber = Subscriber(
            id=uuid.uuid4(), tenant_id=tenant_a.id, email="consumed@test.com", status="pending",
        )
        db_session.add(subscriber)
        await db_session.flush()

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        ct = ConfirmationToken(
            id=uuid.uuid4(), tenant_id=tenant_a.id, subscriber_id=subscriber.id,
            token_hash=token_hash, action="confirm_subscribe",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
            consumed_at=datetime.now(timezone.utc),  # already consumed
        )
        db_session.add(ct)
        await db_session.flush()
        await db_session.commit()

        audit = AuditService(db_session, tenant_a.id)
        service = SubscriptionService(db_session, tenant_a.id, audit)

        with pytest.raises(ValueError, match="invalid, expired, or already used"):
            await service.confirm_token(raw_token)

    async def test_revoked_token_rejected(self, db_session: AsyncSession, tenant_a: Tenant):
        subscriber = Subscriber(
            id=uuid.uuid4(), tenant_id=tenant_a.id, email="revoked@test.com", status="pending",
        )
        db_session.add(subscriber)
        await db_session.flush()

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        ct = ConfirmationToken(
            id=uuid.uuid4(), tenant_id=tenant_a.id, subscriber_id=subscriber.id,
            token_hash=token_hash, action="confirm_subscribe",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
            revoked_at=datetime.now(timezone.utc),  # revoked
        )
        db_session.add(ct)
        await db_session.flush()
        await db_session.commit()

        audit = AuditService(db_session, tenant_a.id)
        service = SubscriptionService(db_session, tenant_a.id, audit)

        with pytest.raises(ValueError, match="invalid, expired, or already used"):
            await service.confirm_token(raw_token)

    async def test_new_token_revokes_old(self, db_session: AsyncSession, tenant_a: Tenant):
        audit = AuditService(db_session, tenant_a.id)
        service = SubscriptionService(db_session, tenant_a.id, audit)

        # First token
        token1 = await service.initiate_subscribe("revoke-old@test.com", source="test")
        # Second token for same email should revoke the first
        token2 = await service.initiate_subscribe("revoke-old@test.com", source="test")

        # First token should now be invalid
        with pytest.raises(ValueError, match="invalid, expired, or already used"):
            await service.confirm_token(token1)

        # Second token should work
        subscriber = await service.confirm_token(token2)
        assert subscriber.status == "confirmed"
