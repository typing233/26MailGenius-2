from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.template_engine import (
    extract_variables,
    render_template,
    sanitize_html,
    validate_template_source,
)
from app.exceptions import AppException
from app.models.template import EmailTemplate, TemplateVersion


class TemplateService:
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def create(self, data: dict, user_id: uuid.UUID | None = None) -> EmailTemplate:
        errors = validate_template_source(data["html_body"])
        if errors:
            raise AppException(status_code=422, detail="Template validation failed", extra={"errors": errors})

        data["html_body"] = sanitize_html(data["html_body"])
        template = EmailTemplate(tenant_id=self.tenant_id, **data)
        self.db.add(template)
        await self.db.flush()

        version = TemplateVersion(
            tenant_id=self.tenant_id,
            template_id=template.id,
            version=1,
            subject=template.subject,
            html_body=template.html_body,
            text_body=template.text_body,
            variables_schema=template.variables_schema,
            change_note="Initial version",
            created_by=user_id,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def get(self, template_id: uuid.UUID) -> EmailTemplate:
        stmt = select(EmailTemplate).where(
            EmailTemplate.id == template_id,
            EmailTemplate.tenant_id == self.tenant_id,
            EmailTemplate.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        template = result.scalar_one_or_none()
        if not template:
            raise AppException(status_code=404, detail="Template not found")
        return template

    async def list(self, category: str | None = None, search: str | None = None, offset: int = 0, limit: int = 20) -> tuple[list[EmailTemplate], int]:
        base = select(EmailTemplate).where(
            EmailTemplate.tenant_id == self.tenant_id,
            EmailTemplate.deleted_at.is_(None),
        )
        if category:
            base = base.where(EmailTemplate.category == category)
        if search:
            base = base.where(EmailTemplate.name.ilike(f"%{search}%"))

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = base.order_by(EmailTemplate.updated_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def update(self, template_id: uuid.UUID, data: dict, user_id: uuid.UUID | None = None) -> EmailTemplate:
        template = await self.get(template_id)

        if "html_body" in data and data["html_body"] is not None:
            errors = validate_template_source(data["html_body"])
            if errors:
                raise AppException(status_code=422, detail="Template validation failed", extra={"errors": errors})
            data["html_body"] = sanitize_html(data["html_body"])

        change_note = data.pop("change_note", None)

        for key, value in data.items():
            if value is not None:
                setattr(template, key, value)
        template.version += 1

        version = TemplateVersion(
            tenant_id=self.tenant_id,
            template_id=template.id,
            version=template.version,
            subject=template.subject,
            html_body=template.html_body,
            text_body=template.text_body,
            variables_schema=template.variables_schema,
            change_note=change_note,
            created_by=user_id,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def delete(self, template_id: uuid.UUID) -> None:
        template = await self.get(template_id)
        from datetime import datetime, timezone
        template.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()

    async def get_versions(self, template_id: uuid.UUID) -> list[TemplateVersion]:
        await self.get(template_id)
        stmt = select(TemplateVersion).where(
            TemplateVersion.template_id == template_id,
            TemplateVersion.tenant_id == self.tenant_id,
        ).order_by(TemplateVersion.version.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_version(self, template_id: uuid.UUID, version: int) -> TemplateVersion:
        stmt = select(TemplateVersion).where(
            TemplateVersion.template_id == template_id,
            TemplateVersion.tenant_id == self.tenant_id,
            TemplateVersion.version == version,
        )
        result = await self.db.execute(stmt)
        ver = result.scalar_one_or_none()
        if not ver:
            raise AppException(status_code=404, detail="Version not found")
        return ver

    async def restore_version(self, template_id: uuid.UUID, version: int, user_id: uuid.UUID | None = None) -> EmailTemplate:
        ver = await self.get_version(template_id, version)
        return await self.update(template_id, {
            "subject": ver.subject,
            "html_body": ver.html_body,
            "text_body": ver.text_body,
            "variables_schema": ver.variables_schema,
            "change_note": f"Restored from version {version}",
        }, user_id=user_id)

    async def preview(self, template_id: uuid.UUID, variables: dict[str, Any]) -> dict[str, str]:
        template = await self.get(template_id)
        rendered_subject = render_template(template.subject, variables)
        rendered_html = render_template(template.html_body, variables)
        rendered_text = render_template(template.text_body, variables) if template.text_body else None
        return {"subject": rendered_subject, "html": rendered_html, "text": rendered_text}

    async def validate(self, template_id: uuid.UUID) -> dict:
        template = await self.get(template_id)
        errors = validate_template_source(template.html_body)
        errors += validate_template_source(template.subject)
        variables_found = extract_variables(template.html_body)
        return {"valid": len(errors) == 0, "errors": errors, "variables_found": variables_found}

    def render_test(self, html_body: str, variables: dict[str, Any]) -> dict:
        errors = validate_template_source(html_body)
        if errors:
            return {"valid": False, "errors": errors, "rendered": None}
        rendered = render_template(html_body, variables)
        return {"valid": True, "errors": [], "rendered": sanitize_html(rendered)}
