import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TemplateCreate(BaseModel):
    name: str = Field(max_length=255)
    subject: str = Field(max_length=500)
    html_body: str
    text_body: str | None = None
    variables_schema: list[dict[str, Any]] = Field(default_factory=list)
    category: str = "marketing"


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, max_length=500)
    html_body: str | None = None
    text_body: str | None = None
    variables_schema: list[dict[str, Any]] | None = None
    category: str | None = None
    is_active: bool | None = None
    change_note: str | None = Field(default=None, max_length=500)


class TemplateResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    subject: str
    html_body: str
    text_body: str | None
    variables_schema: list[dict[str, Any]]
    category: str
    thumbnail_url: str | None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    id: uuid.UUID
    name: str
    subject: str
    category: str
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateVersionResponse(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    version: int
    subject: str
    html_body: str
    text_body: str | None
    variables_schema: list[dict[str, Any]] | None
    change_note: str | None
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplatePreviewRequest(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)


class TemplateRenderTestRequest(BaseModel):
    html_body: str
    subject: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)


class TemplateValidateResponse(BaseModel):
    valid: bool
    errors: list[dict[str, str]]
    variables_found: list[str]
