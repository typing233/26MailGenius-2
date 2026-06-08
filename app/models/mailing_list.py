import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, VersionMixin


class MailingList(Base, TenantMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    __tablename__ = "mailing_lists"
    __table_args__ = (
        Index(
            "uq_mailing_lists_tenant_name_active",
            "tenant_id", "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    list_type = Column(String(50), nullable=False, default="standard")

    subscribers = relationship("ListSubscriber", back_populates="mailing_list", lazy="selectin")


class ListSubscriber(Base, TenantMixin, TimestampMixin, VersionMixin):
    __tablename__ = "list_subscribers"
    __table_args__ = (
        # Only enforce uniqueness for active (non-unsubscribed) associations.
        # This allows re-join after unsubscribe while preserving history rows.
        Index(
            "uq_list_subscribers_active",
            "tenant_id", "list_id", "subscriber_id",
            unique=True,
            postgresql_where=text("unsubscribed_at IS NULL"),
        ),
        Index("ix_list_subscribers_list", "list_id"),
        Index("ix_list_subscribers_subscriber", "subscriber_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_id = Column(UUID(as_uuid=True), ForeignKey("mailing_lists.id"), nullable=False)
    subscriber_id = Column(UUID(as_uuid=True), ForeignKey("subscribers.id"), nullable=False)
    subscribed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    unsubscribed_at = Column(DateTime(timezone=True), nullable=True)

    mailing_list = relationship("MailingList", back_populates="subscribers")
    subscriber = relationship("Subscriber", back_populates="list_associations")
