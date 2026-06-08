import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_filter import TenantQuery
from app.models.subscriber import Subscriber
from app.models.tenant import Tenant


@pytest.mark.asyncio
class TestTenantIsolation:
    async def test_tenant_query_filters_by_tenant(self, db_session: AsyncSession, tenant_a: Tenant, tenant_b: Tenant):
        sub_a = Subscriber(id=uuid.uuid4(), tenant_id=tenant_a.id, email="user@a.com", status="pending")
        sub_b = Subscriber(id=uuid.uuid4(), tenant_id=tenant_b.id, email="user@b.com", status="pending")
        db_session.add_all([sub_a, sub_b])
        await db_session.flush()

        tq_a = TenantQuery(db_session, tenant_a.id)
        tq_b = TenantQuery(db_session, tenant_b.id)

        result_a = await db_session.execute(tq_a.query(Subscriber))
        subs_a = result_a.scalars().all()

        result_b = await db_session.execute(tq_b.query(Subscriber))
        subs_b = result_b.scalars().all()

        assert len(subs_a) == 1
        assert subs_a[0].email == "user@a.com"
        assert len(subs_b) == 1
        assert subs_b[0].email == "user@b.com"

    async def test_get_returns_none_for_other_tenant(self, db_session: AsyncSession, tenant_a: Tenant, tenant_b: Tenant):
        sub = Subscriber(id=uuid.uuid4(), tenant_id=tenant_a.id, email="secret@a.com", status="pending")
        db_session.add(sub)
        await db_session.flush()

        tq_b = TenantQuery(db_session, tenant_b.id)
        result = await tq_b.get(Subscriber, sub.id)
        assert result is None

    async def test_soft_deleted_records_invisible(self, db_session: AsyncSession, tenant_a: Tenant):
        from datetime import datetime, timezone

        sub = Subscriber(
            id=uuid.uuid4(), tenant_id=tenant_a.id, email="deleted@a.com",
            status="pending", deleted_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        await db_session.flush()

        tq = TenantQuery(db_session, tenant_a.id)
        result = await tq.get(Subscriber, sub.id)
        assert result is None

    async def test_cannot_create_model_without_tenant_id(self, db_session: AsyncSession):
        sub = Subscriber(id=uuid.uuid4(), email="no-tenant@test.com", status="pending")
        db_session.add(sub)

        with pytest.raises(ValueError, match="tenant_id must be set"):
            await db_session.flush()
