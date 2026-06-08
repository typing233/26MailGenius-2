import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


class PaginationParams(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    offset: int
    limit: int


class SubscriberFilter(BaseModel):
    email: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None
    name: Optional[str] = None


class SubscriberCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    custom_fields: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    source: Optional[str] = None


class SubscriberUpdate(BaseModel):
    name: Optional[str] = None
    custom_fields: Optional[dict] = None
    tags: Optional[list[str]] = None


class SubscriberResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: Optional[str]
    status: str
    custom_fields: dict
    tags: list
    source: Optional[str]
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubscriberMergeRequest(BaseModel):
    primary_id: uuid.UUID
    duplicate_ids: list[uuid.UUID]
