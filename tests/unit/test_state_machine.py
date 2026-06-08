import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.confirmation import ConfirmationToken
from app.models.mailing_list import ListSubscriber, MailingList
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

    async def test_subscribe_with_list_id_associates_subscriber(self, setup):
        service, session, tenant = setup

        # Create a list
        ml = MailingList(id=uuid.uuid4(), tenant_id=tenant.id, name="Test List SM")
        session.add(ml)
        await session.flush()

        token = await service.initiate_subscribe("list-assoc@test.com", source="test", list_id=ml.id, name="Test User")
        subscriber = await service.confirm_token(token)
        assert subscriber.status == "confirmed"
        assert subscriber.name == "Test User"

        # Verify list association was created
        from sqlalchemy import select
        stmt = select(ListSubscriber).where(
            ListSubscriber.subscriber_id == subscriber.id,
            ListSubscriber.list_id == ml.id,
            ListSubscriber.unsubscribed_at.is_(None),
        )
        result = await session.execute(stmt)
        assoc = result.scalar_one_or_none()
        assert assoc is not None

    async def test_unsubscribe_flow_confirmed_to_unsubscribed(self, setup):
        service, session, tenant = setup
        # First subscribe
        token = await service.initiate_subscribe("unsub@test.com", source="test")
        await service.confirm_token(token)

        # Get subscriber
        from sqlalchemy import select
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

        # Verify unsubscribed
        await session.refresh(subscriber)
        assert subscriber.status == "unsubscribed"

        # Resubscribe — should go directly to confirmed (shortcut unsubscribed -> confirmed)
        new_token = await service.initiate_subscribe("resub@test.com", source="test")
        resubbed = await service.confirm_token(new_token)
        assert resubbed.status == "confirmed"

    async def test_invalid_transition_pending_cannot_unsubscribe(self, db_session: AsyncSession, tenant_a: Tenant):
        subscriber = Subscriber(
            id=uuid.uuid4(), tenant_id=tenant_a.id, email="invalid-trans@test.com", status="pending",
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

    async def test_double_confirm_same_token_fails(self, setup):
        """Token replay protection: using same token twice fails."""
        service, session, tenant = setup
        token = await service.initiate_subscribe("replay@test.com", source="test")
        await service.confirm_token(token)

        # Second use of same token should fail
        with pytest.raises(ValueError, match="invalid, expired, or already used"):
            await service.confirm_token(token)

    async def test_unsubscribe_from_specific_list(self, setup):
        """Unsubscribe from a specific list removes the association."""
        service, session, tenant = setup

        ml = MailingList(id=uuid.uuid4(), tenant_id=tenant.id, name="Unsub List Test")
        session.add(ml)
        await session.flush()

        # Subscribe to list
        token = await service.initiate_subscribe("list-unsub@test.com", source="test", list_id=ml.id)
        subscriber = await service.confirm_token(token)

        # Unsubscribe from list
        unsub_token = await service.initiate_unsubscribe(subscriber.id, list_id=ml.id)
        await service.confirm_token(unsub_token)

        # Verify list association is removed
        from sqlalchemy import select
        stmt = select(ListSubscriber).where(
            ListSubscriber.subscriber_id == subscriber.id,
            ListSubscriber.list_id == ml.id,
            ListSubscriber.unsubscribed_at.is_(None),
        )
        result = await session.execute(stmt)
        assert result.scalar_one_or_none() is None
