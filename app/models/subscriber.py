import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, VersionMixin


class Subscriber(Base, TenantMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    __tablename__ = "subscribers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_subscribers_tenant_email"),
        Index("ix_subscribers_tenant_status", "tenant_id", "status"),
        Index("ix_subscribers_tenant_email_lower", "tenant_id", func.lower("email")),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(320), nullable=False)
    name = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    custom_fields = Column(JSONB, nullable=False, server_default="{}")
    tags = Column(JSONB, nullable=False, server_default="[]")
    source = Column(String(50), nullable=True)

    list_associations = relationship("ListSubscriber", back_populates="subscriber", lazy="selectin")
