import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, event, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Session, declared_attr


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))


class TenantMixin:
    @declared_attr
    def tenant_id(cls):
        return Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)


class SoftDeleteMixin:
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class VersionMixin:
    version = Column(Integer, nullable=False, default=1)


@event.listens_for(Session, "before_flush")
def enforce_tenant_id(session, flush_context, instances):
    for obj in session.new:
        if hasattr(obj, "tenant_id") and obj.tenant_id is None:
            raise ValueError(f"tenant_id must be set on {type(obj).__name__}")
