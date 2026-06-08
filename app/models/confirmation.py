import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TenantMixin


class ConfirmationToken(Base, TenantMixin):
    __tablename__ = "confirmation_tokens"
    __table_args__ = (
        Index("ix_confirmation_token_hash_active", "token_hash", postgresql_where="consumed_at IS NULL AND revoked_at IS NULL"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscriber_id = Column(UUID(as_uuid=True), ForeignKey("subscribers.id"), nullable=False)
    list_id = Column(UUID(as_uuid=True), ForeignKey("mailing_lists.id"), nullable=True)
    token_hash = Column(String(255), nullable=False, unique=True)
    action = Column(String(20), nullable=False)  # confirm_subscribe, confirm_unsubscribe
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
