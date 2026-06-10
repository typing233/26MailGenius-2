import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class SmtpChannel(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "smtp_channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=587)
    username = Column(String(255), nullable=True)
    password_encrypted = Column(LargeBinary, nullable=True)
    use_tls = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    daily_limit = Column(Integer, default=10000)
    hourly_limit = Column(Integer, default=1000)
    # Health
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, default=0)
