import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, VersionMixin


class Campaign(Base, TenantMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    status = Column(String(20), default="draft", nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("email_templates.id"), nullable=False)
    template_version = Column(Integer, nullable=True)
    sender_name = Column(String(100), nullable=True)
    sender_email = Column(String(255), nullable=True)
    reply_to = Column(String(255), nullable=True)
    # Targeting
    list_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)
    segment_rule_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)
    exclusion_list_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)
    # Scheduling
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(String(50), default="UTC")
    # Batch config
    batch_size = Column(Integer, default=500)
    batch_interval_seconds = Column(Integer, default=10)
    # Stats
    total_recipients = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    opened_count = Column(Integer, default=0)
    clicked_count = Column(Integer, default=0)
    bounced_count = Column(Integer, default=0)
    unsubscribed_count = Column(Integer, default=0)
    # Metadata
    tags = Column(JSONB, default=list)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)

    jobs = relationship("CampaignJob", back_populates="campaign", lazy="dynamic")


class CampaignJob(Base, TenantMixin, TimestampMixin):
    __tablename__ = "campaign_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    subscriber_id = Column(UUID(as_uuid=True), ForeignKey("subscribers.id"), nullable=False)
    batch_number = Column(Integer, nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    idempotency_key = Column(String(100), nullable=False, unique=True)
    message_id = Column(String(255), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    error_chain = Column(JSONB, default=list)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    campaign = relationship("Campaign", back_populates="jobs")
