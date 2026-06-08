import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.tenant_filter import TenantQuery
from app.models.confirmation import ConfirmationToken
from app.models.subscriber import Subscriber
from app.services.audit_service import AuditService


class SubscriberStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    UNSUBSCRIBED = "unsubscribed"


VALID_TRANSITIONS = {
    (SubscriberStatus.PENDING, "confirm"): SubscriberStatus.CONFIRMED,
    (SubscriberStatus.CONFIRMED, "unsubscribe"): SubscriberStatus.UNSUBSCRIBED,
    (SubscriberStatus.UNSUBSCRIBED, "resubscribe"): SubscriberStatus.PENDING,
}

ACTION_TO_TRANSITION = {
    "confirm_subscribe": "confirm",
    "confirm_unsubscribe": "unsubscribe",
}


class SubscriptionService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, audit: AuditService):
        self.session = session
        self.tenant_id = tenant_id
        self.tq = TenantQuery(session, tenant_id)
        self.audit = audit

    async def initiate_subscribe(self, email: str, source: str = "form") -> str:
        async with self.session.begin_nested():
            subscriber = await self._get_or_create_subscriber(email, source)
            await self._revoke_existing_tokens(subscriber.id, "confirm_subscribe")
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

            confirmation = ConfirmationToken(
                tenant_id=self.tenant_id,
                subscriber_id=subscriber.id,
                token_hash=token_hash,
                action="confirm_subscribe",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.confirmation_token_ttl_hours),
            )
            self.session.add(confirmation)
            await self.audit.log("initiate_subscribe", "subscriber", subscriber.id, changes={"email": email})

        await self.session.commit()
        return raw_token

    async def initiate_unsubscribe(self, subscriber_id: uuid.UUID) -> str:
        subscriber = await self.tq.get_or_404(Subscriber, subscriber_id)

        async with self.session.begin_nested():
            await self._revoke_existing_tokens(subscriber.id, "confirm_unsubscribe")
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

            confirmation = ConfirmationToken(
                tenant_id=self.tenant_id,
                subscriber_id=subscriber.id,
                token_hash=token_hash,
                action="confirm_unsubscribe",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.confirmation_token_ttl_hours),
            )
            self.session.add(confirmation)
            await self.audit.log("initiate_unsubscribe", "subscriber", subscriber.id)

        await self.session.commit()
        return raw_token

    async def confirm_token(self, raw_token: str) -> Subscriber:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        async with self.session.begin_nested():
            # Lock the token row to prevent race conditions
            stmt = (
                select(ConfirmationToken)
                .where(
                    ConfirmationToken.token_hash == token_hash,
                    ConfirmationToken.consumed_at.is_(None),
                    ConfirmationToken.revoked_at.is_(None),
                    ConfirmationToken.expires_at > datetime.now(timezone.utc),
                )
                .with_for_update()
            )
            result = await self.session.execute(stmt)
            token = result.scalar_one_or_none()

            if token is None:
                raise ValueError("Token is invalid, expired, or already used")

            # Lock subscriber row
            sub_stmt = select(Subscriber).where(Subscriber.id == token.subscriber_id).with_for_update()
            sub_result = await self.session.execute(sub_stmt)
            subscriber = sub_result.scalar_one()

            old_status = subscriber.status
            transition_action = ACTION_TO_TRANSITION.get(token.action)
            new_status = VALID_TRANSITIONS.get((SubscriberStatus(old_status), transition_action))

            if new_status is None:
                raise ValueError(f"Invalid state transition: cannot {transition_action} from {old_status}")

            subscriber.status = new_status.value
            subscriber.updated_at = datetime.now(timezone.utc)
            subscriber.version += 1

            # Mark token as consumed (single-use)
            token.consumed_at = datetime.now(timezone.utc)

            await self.audit.log(
                f"status_change_{transition_action}",
                "subscriber",
                subscriber.id,
                changes={"status": {"before": old_status, "after": new_status.value}},
            )

        await self.session.commit()
        return subscriber

    async def _get_or_create_subscriber(self, email: str, source: str) -> Subscriber:
        stmt = self.tq.query(Subscriber).where(Subscriber.email == email)
        result = await self.session.execute(stmt)
        subscriber = result.scalar_one_or_none()

        if subscriber is None:
            subscriber = Subscriber(
                tenant_id=self.tenant_id,
                email=email,
                status=SubscriberStatus.PENDING.value,
                source=source,
            )
            self.session.add(subscriber)
            await self.session.flush()

        return subscriber

    async def _revoke_existing_tokens(self, subscriber_id: uuid.UUID, action: str) -> None:
        stmt = (
            update(ConfirmationToken)
            .where(
                ConfirmationToken.subscriber_id == subscriber_id,
                ConfirmationToken.action == action,
                ConfirmationToken.consumed_at.is_(None),
                ConfirmationToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
