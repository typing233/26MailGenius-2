import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TenantMixin, TimestampMixin


class EmbedFormConfig(Base, TenantMixin, TimestampMixin):
    __tablename__ = "embed_form_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_id = Column(UUID(as_uuid=True), ForeignKey("mailing_lists.id"), nullable=False)
    allowed_domains = Column(JSONB, nullable=False, server_default="[]")
    honeypot_field_name = Column(String(50), nullable=False, default="website")
    captcha_enabled = Column(Boolean, nullable=False, default=False)
    captcha_provider = Column(String(20), nullable=True)
    captcha_site_key = Column(String(255), nullable=True)
    captcha_secret_key = Column(String(255), nullable=True)
    rate_limit_per_ip = Column(Integer, nullable=False, default=5)
    custom_css = Column(Text, nullable=True)
    redirect_url = Column(String(500), nullable=True)
