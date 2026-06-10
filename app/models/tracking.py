import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET, UUID

from app.models.base import Base, TenantMixin, TimestampMixin


class TrackingEvent(Base, TenantMixin, TimestampMixin):
    __tablename__ = "tracking_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), nullable=False)
    subscriber_id = Column(UUID(as_uuid=True), nullable=False)
    job_id = Column(UUID(as_uuid=True), nullable=True)
    event_type = Column(String(20), nullable=False)
    link_url = Column(Text, nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(INET, nullable=True)
    fingerprint = Column(String(100), nullable=True)
    is_first = Column(Boolean, default=False)
    is_machine = Column(Boolean, default=False)
    occurred_at = Column(DateTime(timezone=True), server_default="now()")


class TrackingLink(Base, TenantMixin, TimestampMixin):
    __tablename__ = "tracking_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), nullable=False)
    original_url = Column(Text, nullable=False)
    tracking_code = Column(String(32), nullable=False, unique=True)
    click_count = Column(Integer, default=0)
    unique_clicks = Column(Integer, default=0)
