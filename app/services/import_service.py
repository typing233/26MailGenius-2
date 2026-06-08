import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.tenant_filter import TenantQuery
from app.database import async_session_factory
from app.models.import_job import ImportJob
from app.models.subscriber import Subscriber
from app.services.audit_service import AuditService
from app.utils.csv_processor import parse_csv_chunks_streaming, validate_csv_row


class ImportService:
    def __init__(self, session: AsyncSession, tq: TenantQuery, audit: AuditService):
        self.session = session
        self.tq = tq
        self.audit = audit

    async def initiate_import(
        self, file_reader, filename: str, tenant_id: uuid.UUID, user_id: uuid.UUID, dedup_key: str | None = None
    ) -> ImportJob:
        # Idempotent retry: if dedup_key exists for any non-failed status, return the existing job
        if dedup_key:
            existing = await self._find_by_dedup_key(tenant_id, dedup_key)
            if existing and existing.status in ("pending", "processing", "completed", "partial"):
                return existing

        job = ImportJob(
            tenant_id=tenant_id,
            user_id=user_id,
            dedup_key=dedup_key,
            filename=filename,
            status="pending",
        )
        self.session.add(job)
        await self.session.commit()

        # Launch background processing with the streaming reader
        asyncio.create_task(self._process_import(job.id, file_reader, tenant_id))
        return job

    async def get_job_status(self, job_id: uuid.UUID) -> ImportJob:
        return await self.tq.get_or_404(ImportJob, job_id)

    async def _process_import(self, job_id: uuid.UUID, file_reader, tenant_id: uuid.UUID) -> None:
        async with async_session_factory() as session:
            stmt = select(ImportJob).where(ImportJob.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one()

            job.status = "processing"
            job.started_at = datetime.now(timezone.utc)
            await session.commit()

            errors = []
            total_rows = 0
            success_rows = 0

            try:
                async for chunk in parse_csv_chunks_streaming(file_reader, settings.import_chunk_size):
                    chunk_errors = await self._persist_chunk(session, tenant_id, chunk)
                    total_rows += len(chunk)
                    success_rows += len(chunk) - len(chunk_errors)
                    errors.extend(chunk_errors)
                    await session.commit()

                job.total_rows = total_rows
                job.processed_rows = total_rows
                job.success_rows = success_rows
                job.error_rows = len(errors)
                job.error_details = errors[:1000]
                job.status = "completed" if not errors else "partial"

            except Exception as e:
                job.status = "failed"
                job.error_details = [{"error": str(e)}]

            job.completed_at = datetime.now(timezone.utc)
            await session.commit()

    async def _persist_chunk(self, session: AsyncSession, tenant_id: uuid.UUID, chunk: list[dict]) -> list[dict]:
        errors = []
        async with session.begin_nested():
            for row in chunk:
                parsed, error = validate_csv_row(row)
                if error:
                    errors.append({"row": row.get("_row_num"), "error": error})
                    continue

                # Check duplicate within tenant
                existing_stmt = (
                    select(Subscriber)
                    .where(
                        Subscriber.tenant_id == tenant_id,
                        func.lower(Subscriber.email) == parsed["email"],
                        Subscriber.deleted_at.is_(None),
                    )
                )
                existing_result = await session.execute(existing_stmt)
                if existing_result.scalar_one_or_none():
                    errors.append({"row": row.get("_row_num"), "error": f"duplicate: {parsed['email']}"})
                    continue

                subscriber = Subscriber(
                    tenant_id=tenant_id,
                    email=parsed["email"],
                    name=parsed["name"],
                    status="pending",
                    custom_fields=parsed["custom_fields"],
                    tags=parsed["tags"],
                    source="import",
                )
                session.add(subscriber)

        return errors

    async def _find_by_dedup_key(self, tenant_id: uuid.UUID, dedup_key: str) -> ImportJob | None:
        stmt = select(ImportJob).where(
            ImportJob.tenant_id == tenant_id,
            ImportJob.dedup_key == dedup_key,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
