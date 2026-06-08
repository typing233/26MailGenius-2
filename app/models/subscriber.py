import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, VersionMixin


class Subscriber(Base, TenantMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    __tablename__ = "subscribers"
    __table_args__ = (
        Index(
            "uq_subscribers_tenant_email_active",
            "tenant_id", "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_subscribers_tenant_status", "tenant_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(320), nullable=False)
    name = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    custom_fields = Column(JSONB, nullable=False, server_default="{}")
    tags = Column(JSONB, nullable=False, server_default="[]")
    source = Column(String(50), nullable=True)

    list_associations = relationship("ListSubscriber", back_populates="subscriber", lazy="selectin")
