import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TenantMixin, TimestampMixin


class DeadLetterJob(Base, TenantMixin, TimestampMixin):
    __tablename__ = "dead_letter_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_job_id = Column(UUID(as_uuid=True), ForeignKey("campaign_jobs.id"), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), nullable=False)
    subscriber_id = Column(UUID(as_uuid=True), nullable=False)
    final_error = Column(Text, nullable=True)
    error_chain = Column(JSONB, nullable=True)
    moved_at = Column(DateTime(timezone=True), server_default="now()")
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution = Column(String(50), nullable=True)
