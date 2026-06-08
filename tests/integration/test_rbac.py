import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.subscriber import Subscriber
from app.models.tenant import Tenant
from app.models.user import User


@pytest.mark.asyncio
class TestRBAC:
    async def test_member_cannot_delete_subscriber(self, client: AsyncClient, member_token: str, db_session, tenant_a):
        sub = Subscriber(id=uuid.uuid4(), tenant_id=tenant_a.id, email="rbac-del@test.com", status="pending")
        db_session.add(sub)
        await db_session.flush()

        resp = await client.delete(
            f"/api/v1/subscribers/{sub.id}",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert resp.status_code == 403

    async def test_member_can_read_subscribers(self, client: AsyncClient, member_token: str):
        resp = await client.get(
            "/api/v1/subscribers",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert resp.status_code == 200

    async def test_tenant_admin_can_delete_subscriber(self, client: AsyncClient, token_a: str, db_session, tenant_a):
        sub = Subscriber(id=uuid.uuid4(), tenant_id=tenant_a.id, email="rbac-admin-del@test.com", status="pending")
        db_session.add(sub)
        await db_session.flush()

        resp = await client.delete(
            f"/api/v1/subscribers/{sub.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 204

    async def test_cross_tenant_access_returns_404(self, client: AsyncClient, token_b: str, db_session, tenant_a):
        sub = Subscriber(id=uuid.uuid4(), tenant_id=tenant_a.id, email="cross-tenant@test.com", status="pending")
        db_session.add(sub)
        await db_session.flush()

        resp = await client.get(
            f"/api/v1/subscribers/{sub.id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        # Returns 404, not 403, to avoid information leakage
        assert resp.status_code == 404

    async def test_member_cannot_manage_lists(self, client: AsyncClient, member_token: str):
        resp = await client.post(
            "/api/v1/lists",
            json={"name": "Unauthorized List"},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert resp.status_code == 403

    async def test_member_cannot_import(self, client: AsyncClient, member_token: str):
        resp = await client.post(
            "/api/v1/import-export/import",
            files={"file": ("test.csv", b"email\ntest@test.com", "text/csv")},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert resp.status_code == 403
