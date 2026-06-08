import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_filter import TenantQuery
from app.models.subscriber import Subscriber
from app.models.tenant import Tenant
from app.services.audit_service import AuditService
from app.services.import_service import ImportService
from app.utils.csv_processor import (
    format_csv_field,
    generate_csv_export_line,
    parse_csv_chunks,
    validate_csv_row,
)


class TestCSVValidation:
    def test_validate_csv_row_valid(self):
        row = {"email": "user@test.com", "name": "Test User", "tags": "tag1;tag2"}
        parsed, error = validate_csv_row(row)
        assert error is None
        assert parsed["email"] == "user@test.com"
        assert parsed["name"] == "Test User"
        assert parsed["tags"] == ["tag1", "tag2"]

    def test_validate_csv_row_invalid_email(self):
        row = {"email": "invalid", "name": "Bad User"}
        parsed, error = validate_csv_row(row)
        assert parsed is None
        assert "Invalid email" in error

    def test_validate_csv_row_empty_email(self):
        row = {"email": "", "name": "No Email"}
        parsed, error = validate_csv_row(row)
        assert parsed is None
        assert "Invalid email" in error

    def test_validate_csv_row_custom_fields(self):
        row = {"email": "user@test.com", "name": "User", "tags": "", "company": "Acme", "role": "dev"}
        parsed, error = validate_csv_row(row)
        assert error is None
        assert parsed["custom_fields"] == {"company": "Acme", "role": "dev"}


class TestCSVEscaping:
    def test_format_field_no_special_chars(self):
        assert format_csv_field("hello") == "hello"

    def test_format_field_with_comma(self):
        assert format_csv_field("hello, world") == '"hello, world"'

    def test_format_field_with_quotes(self):
        assert format_csv_field('say "hi"') == '"say ""hi"""'

    def test_format_field_with_newline(self):
        assert format_csv_field("line1\nline2") == '"line1\nline2"'

    def test_export_line_with_special_chars(self):
        class FakeSub:
            email = "user@test.com"
            name = 'O"Brien, Jr.'
            status = "confirmed"
            tags = ["tag,1", "tag2"]

        line = generate_csv_export_line(FakeSub())
        assert '"O""Brien, Jr."' in line
        assert '"tag,1;tag2"' in line


@pytest.mark.asyncio
class TestCSVChunking:
    async def test_parse_csv_chunks_splitting(self):
        content = "email,name\n"
        for i in range(10):
            content += f"user{i}@test.com,User {i}\n"

        chunks = []
        async for chunk in parse_csv_chunks(content.encode(), chunk_size=3):
            chunks.append(chunk)

        assert len(chunks) == 4  # 3+3+3+1
        assert len(chunks[0]) == 3
        assert len(chunks[-1]) == 1

    async def test_parse_csv_handles_quoted_fields(self):
        content = 'email,name,tags\nuser@test.com,"Smith, John","tag1;tag2"\n'

        chunks = []
        async for chunk in parse_csv_chunks(content.encode(), chunk_size=100):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0][0]["name"] == "Smith, John"
        assert chunks[0][0]["tags"] == "tag1;tag2"


@pytest.mark.asyncio
class TestImportIdempotency:
    async def test_import_idempotent_pending(self, db_session: AsyncSession, tenant_a: Tenant, user_a):
        tq = TenantQuery(db_session, tenant_a.id)
        audit = AuditService(db_session, tenant_a.id, user_a.id)
        service = ImportService(db_session, tq, audit)

        async def _reader():
            yield b"email,name\ntest-idem@test.com,Test\n"

        job1 = await service.initiate_import(
            file_reader=_reader(),
            filename="test.csv",
            tenant_id=tenant_a.id,
            user_id=user_a.id,
            dedup_key="idem-key-1",
        )

        # Second call with same dedup_key while first is pending/processing should return same job
        job2 = await service.initiate_import(
            file_reader=_reader(),
            filename="test.csv",
            tenant_id=tenant_a.id,
            user_id=user_a.id,
            dedup_key="idem-key-1",
        )
        assert job2.id == job1.id

    async def test_import_different_dedup_key_creates_new(self, db_session: AsyncSession, tenant_a: Tenant, user_a):
        tq = TenantQuery(db_session, tenant_a.id)
        audit = AuditService(db_session, tenant_a.id, user_a.id)
        service = ImportService(db_session, tq, audit)

        async def _reader():
            yield b"email,name\ntest-diff@test.com,Test\n"

        job1 = await service.initiate_import(
            file_reader=_reader(), filename="test.csv",
            tenant_id=tenant_a.id, user_id=user_a.id, dedup_key="key-a",
        )
        job2 = await service.initiate_import(
            file_reader=_reader(), filename="test.csv",
            tenant_id=tenant_a.id, user_id=user_a.id, dedup_key="key-b",
        )
        assert job2.id != job1.id
