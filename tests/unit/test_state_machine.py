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
class TestStateMachine:
    @pytest_asyncio.fixture
    async def setup(self, db_session: AsyncSession, tenant_a: Tenant):
        audit = AuditService(db_session, tenant_a.id)
        service = SubscriptionService(db_session, tenant_a.id, audit)
        return service, db_session, tenant_a

    async def test_subscribe_flow_pending_to_confirmed(self, setup):
        service, session, tenant = setup
        token = await service.initiate_subscribe("new@test.com", source="test")
        assert token is not None

        subscriber = await service.confirm_token(token)
        assert subscriber.status == "confirmed"

    async def test_unsubscribe_flow_confirmed_to_unsubscribed(self, setup):
        service, session, tenant = setup
        # First subscribe
        token = await service.initiate_subscribe("unsub@test.com", source="test")
        await service.confirm_token(token)

        # Get subscriber
        from sqlalchemy import select
        from app.models.subscriber import Subscriber

        stmt = select(Subscriber).where(Subscriber.email == "unsub@test.com", Subscriber.tenant_id == tenant.id)
        result = await session.execute(stmt)
        subscriber = result.scalar_one()

        # Initiate unsubscribe
        unsub_token = await service.initiate_unsubscribe(subscriber.id)
        updated = await service.confirm_token(unsub_token)
        assert updated.status == "unsubscribed"

    async def test_resubscribe_after_unsubscribe(self, setup):
        service, session, tenant = setup
        # Subscribe
        token = await service.initiate_subscribe("resub@test.com", source="test")
        await service.confirm_token(token)

        from sqlalchemy import select

        stmt = select(Subscriber).where(Subscriber.email == "resub@test.com", Subscriber.tenant_id == tenant.id)
        result = await session.execute(stmt)
        subscriber = result.scalar_one()

        # Unsubscribe
        unsub_token = await service.initiate_unsubscribe(subscriber.id)
        await service.confirm_token(unsub_token)

        # Resubscribe goes back to pending
        new_token = await service.initiate_subscribe("resub@test.com", source="test")
        resubbed = await service.confirm_token(new_token)
        assert resubbed.status == "confirmed"

    async def test_invalid_transition_raises_error(self, db_session: AsyncSession, tenant_a: Tenant):
        # Create a subscriber already in "pending" status and try to unsubscribe directly
        subscriber = Subscriber(
            id=uuid.uuid4(), tenant_id=tenant_a.id, email="invalid@test.com", status="pending",
        )
        db_session.add(subscriber)
        await db_session.flush()

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        ct = ConfirmationToken(
            id=uuid.uuid4(), tenant_id=tenant_a.id, subscriber_id=subscriber.id,
            token_hash=token_hash, action="confirm_unsubscribe",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        db_session.add(ct)
        await db_session.flush()
        await db_session.commit()

        audit = AuditService(db_session, tenant_a.id)
        service = SubscriptionService(db_session, tenant_a.id, audit)

        with pytest.raises(ValueError, match="Invalid state transition"):
            await service.confirm_token(raw_token)
