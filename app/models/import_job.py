import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TenantMixin, TimestampMixin


class ImportJob(Base, TenantMixin, TimestampMixin):
    __tablename__ = "import_jobs"
    __table_args__ = (
        Index("uq_import_jobs_dedup", "tenant_id", "dedup_key", unique=True, postgresql_where="dedup_key IS NOT NULL"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    dedup_key = Column(String(255), nullable=True)
    filename = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    success_rows = Column(Integer, default=0)
    error_rows = Column(Integer, default=0)
    error_details = Column(JSONB, nullable=False, server_default="[]")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
