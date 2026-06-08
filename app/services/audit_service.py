import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID | None = None, ip_address: str | None = None):
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.ip_address = ip_address

    async def log(self, action: str, entity_type: str, entity_id: uuid.UUID, changes: dict | None = None):
        entry = AuditLog(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes or {},
            ip_address=self.ip_address,
        )
        self.session.add(entry)
