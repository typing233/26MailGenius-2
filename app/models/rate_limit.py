import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TenantMixin, TimestampMixin


class RateLimitCounter(Base, TenantMixin, TimestampMixin):
    __tablename__ = "rate_limit_counters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("smtp_channels.id"), nullable=True)
    window_key = Column(String(50), nullable=False)
    count = Column(Integer, default=0)
    limit_value = Column(Integer, nullable=False)
