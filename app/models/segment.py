import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TenantMixin, TimestampMixin, SoftDeleteMixin


class SegmentRule(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "segment_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    conditions = Column(JSONB, nullable=False)
    estimated_count = Column(Integer, nullable=True)
    last_evaluated = Column(DateTime(timezone=True), nullable=True)
