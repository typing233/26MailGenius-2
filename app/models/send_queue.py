import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TenantMixin, TimestampMixin


class SendQueueJob(Base, TenantMixin, TimestampMixin):
    __tablename__ = "send_queue_jobs"
    __table_args__ = (
        Index("ix_send_queue_status_scheduled", "status", "scheduled_at"),
        Index("ix_send_queue_tenant_campaign", "tenant_id", "campaign_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), nullable=True)
    subscriber_id = Column(UUID(as_uuid=True), ForeignKey("subscribers.id"), nullable=False)
    list_id = Column(UUID(as_uuid=True), ForeignKey("mailing_lists.id"), nullable=True)
    status = Column(String(20), nullable=False, default="queued")
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
