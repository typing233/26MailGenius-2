import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuthFlow:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "password": "securepass123",
            "full_name": "New User",
            "tenant_name": "New Tenant",
            "tenant_slug": "new-tenant-reg",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_register_duplicate_slug_fails(self, client: AsyncClient):
        payload = {
            "email": "first@example.com",
            "password": "securepass123",
            "tenant_name": "Dup Tenant",
            "tenant_slug": "dup-tenant-slug",
        }
        await client.post("/api/v1/auth/register", json=payload)
        resp = await client.post("/api/v1/auth/register", json={**payload, "email": "second@example.com"})
        assert resp.status_code == 409

    async def test_login_success(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "login@example.com",
            "password": "securepass123",
            "tenant_name": "Login Tenant",
            "tenant_slug": "login-tenant",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "login@example.com",
            "password": "securepass123",
            "tenant_slug": "login-tenant",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_tenant_slug_fails(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "tenantfail@example.com",
            "password": "securepass123",
            "tenant_name": "TenantFail",
            "tenant_slug": "tenant-fail",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "tenantfail@example.com",
            "password": "securepass123",
            "tenant_slug": "wrong-slug",
        })
        assert resp.status_code == 401

    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "wrongpw@example.com",
            "password": "securepass123",
            "tenant_name": "WrongPW Tenant",
            "tenant_slug": "wrongpw-tenant",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "wrongpw@example.com",
            "password": "wrongpassword",
            "tenant_slug": "wrongpw-tenant",
        })
        assert resp.status_code == 401

    async def test_me_endpoint(self, client: AsyncClient):
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "me@example.com",
            "password": "securepass123",
            "tenant_name": "Me Tenant",
            "tenant_slug": "me-tenant",
        })
        token = reg_resp.json()["access_token"]

        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"

    async def test_refresh_token_rotation(self, client: AsyncClient):
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "refresh@example.com",
            "password": "securepass123",
            "tenant_name": "Refresh Tenant",
            "tenant_slug": "refresh-tenant",
        })
        refresh_token = reg_resp.json()["refresh_token"]

        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        new_tokens = resp.json()
        assert "access_token" in new_tokens
        assert new_tokens["refresh_token"] != refresh_token

        # Old refresh token should be revoked
        resp2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp2.status_code == 401

    async def test_access_protected_route_without_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/subscribers")
        assert resp.status_code == 401

    async def test_same_email_different_tenants_isolated(self, client: AsyncClient):
        """Same email in different tenants should not cross-authenticate."""
        await client.post("/api/v1/auth/register", json={
            "email": "shared@example.com",
            "password": "password-a",
            "tenant_name": "Tenant A Iso",
            "tenant_slug": "iso-tenant-a",
        })
        await client.post("/api/v1/auth/register", json={
            "email": "shared@example.com",
            "password": "password-b",
            "tenant_name": "Tenant B Iso",
            "tenant_slug": "iso-tenant-b",
        })
        # Login with tenant A password on tenant B should fail
        resp = await client.post("/api/v1/auth/login", json={
            "email": "shared@example.com",
            "password": "password-a",
            "tenant_slug": "iso-tenant-b",
        })
        assert resp.status_code == 401
