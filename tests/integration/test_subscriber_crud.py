import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.subscriber import Subscriber
from app.models.tenant import Tenant


@pytest.mark.asyncio
class TestSubscriberCRUD:
    async def test_create_subscriber(self, client: AsyncClient, token_a: str):
        resp = await client.post(
            "/api/v1/subscribers",
            json={"email": "crud-create@test.com", "name": "Test", "tags": ["vip"]},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "crud-create@test.com"
        assert data["status"] == "pending"
        assert "vip" in data["tags"]

    async def test_create_duplicate_email_fails(self, client: AsyncClient, token_a: str, db_session, tenant_a):
        sub = Subscriber(id=uuid.uuid4(), tenant_id=tenant_a.id, email="dup@test.com", status="pending")
        db_session.add(sub)
        await db_session.flush()

        resp = await client.post(
            "/api/v1/subscribers",
            json={"email": "dup@test.com"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 400

    async def test_list_subscribers_pagination(self, client: AsyncClient, token_a: str, db_session, tenant_a):
        for i in range(5):
            sub = Subscriber(id=uuid.uuid4(), tenant_id=tenant_a.id, email=f"page{i}@test.com", status="pending")
            db_session.add(sub)
        await db_session.flush()

        resp = await client.get(
            "/api/v1/subscribers?limit=2&offset=0",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 2
        assert len(data["items"]) <= 2
        assert data["total"] >= 5

    async def test_filter_subscribers_by_status(self, client: AsyncClient, token_a: str, db_session, tenant_a):
        sub = Subscriber(id=uuid.uuid4(), tenant_id=tenant_a.id, email="confirmed@test.com", status="confirmed")
        db_session.add(sub)
        await db_session.flush()

        resp = await client.get(
            "/api/v1/subscribers?status=confirmed",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "confirmed"

    async def test_update_subscriber(self, client: AsyncClient, token_a: str, db_session, tenant_a):
        sub = Subscriber(id=uuid.uuid4(), tenant_id=tenant_a.id, email="update@test.com", status="pending")
        db_session.add(sub)
        await db_session.flush()

        resp = await client.patch(
            f"/api/v1/subscribers/{sub.id}",
            json={"name": "Updated Name", "tags": ["new-tag"]},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert "new-tag" in resp.json()["tags"]

    async def test_delete_subscriber_soft_delete(self, client: AsyncClient, token_a: str, db_session, tenant_a):
        sub = Subscriber(id=uuid.uuid4(), tenant_id=tenant_a.id, email="softdel@test.com", status="pending")
        db_session.add(sub)
        await db_session.flush()

        resp = await client.delete(
            f"/api/v1/subscribers/{sub.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 204

        # Should not be findable after delete
        resp2 = await client.get(
            f"/api/v1/subscribers/{sub.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp2.status_code == 404
