import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestImportExport:
    async def test_import_csv_accepted(self, client: AsyncClient, token_a: str):
        csv_content = b"email,name,tags\nimport1@test.com,User 1,tag1;tag2\nimport2@test.com,User 2,tag3\n"

        resp = await client.post(
            "/api/v1/import-export/import",
            files={"file": ("subscribers.csv", csv_content, "text/csv")},
            data={"dedup_key": "test-import-1"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] in ("pending", "processing")
        assert data["filename"] == "subscribers.csv"

    async def test_import_status_check(self, client: AsyncClient, token_a: str):
        csv_content = b"email,name\nstatus-check@test.com,SC User\n"

        import_resp = await client.post(
            "/api/v1/import-export/import",
            files={"file": ("test.csv", csv_content, "text/csv")},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        job_id = import_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/import-export/import/{job_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id

    async def test_export_csv(self, client: AsyncClient, token_a: str):
        resp = await client.get(
            "/api/v1/import-export/export",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "email,name,status,tags" in resp.text
