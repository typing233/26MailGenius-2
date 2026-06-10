import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, VersionMixin


class EmailTemplate(Base, TenantMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    __tablename__ = "email_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text, nullable=True)
    variables_schema = Column(JSONB, default=list)
    category = Column(String(50), default="marketing")
    thumbnail_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)

    versions = relationship("TemplateVersion", back_populates="template", lazy="dynamic")


class TemplateVersion(Base, TenantMixin, TimestampMixin):
    __tablename__ = "template_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("email_templates.id"), nullable=False)
    version = Column(Integer, nullable=False)
    subject = Column(String(500), nullable=False)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text, nullable=True)
    variables_schema = Column(JSONB, nullable=True)
    change_note = Column(String(500), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    template = relationship("EmailTemplate", back_populates="versions")
