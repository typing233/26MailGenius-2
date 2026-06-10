import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TenantMixin, TimestampMixin


class CampaignReport(Base, TenantMixin, TimestampMixin):
    __tablename__ = "campaign_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    report_type = Column(String(20), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    metrics = Column(JSONB, nullable=False)
    funnel = Column(JSONB, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default="now()")
