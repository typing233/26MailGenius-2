import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SegmentCondition(BaseModel):
    field: str
    operator: str
    value: Any
    logic: str = "AND"


class SegmentCreate(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = None
    conditions: list[SegmentCondition]


class SegmentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    conditions: list[SegmentCondition] | None = None


class SegmentResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    conditions: list[dict[str, Any]]
    estimated_count: int | None
    last_evaluated: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SegmentEvaluateResponse(BaseModel):
    segment_id: uuid.UUID
    estimated_count: int
    sample_emails: list[str]
