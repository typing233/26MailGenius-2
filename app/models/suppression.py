import uuid

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TenantMixin, TimestampMixin


class SuppressionEntry(Base, TenantMixin, TimestampMixin):
    __tablename__ = "suppression_list"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False)
    reason = Column(String(50), nullable=False)
    source = Column(String(100), nullable=True)
    suppressed_at = Column(DateTime(timezone=True), server_default="now()")
    expires_at = Column(DateTime(timezone=True), nullable=True)
