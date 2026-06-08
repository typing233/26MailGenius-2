import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MailingListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    list_type: str = Field(default="standard", max_length=50)


class MailingListUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    list_type: Optional[str] = None


class MailingListResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    list_type: str
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ListSubscriberAdd(BaseModel):
    subscriber_ids: list[uuid.UUID]
    expected_version: Optional[int] = None


class ListSubscriberRemove(BaseModel):
    subscriber_ids: list[uuid.UUID]


class BulkOperationResult(BaseModel):
    success_count: int
    error_count: int
    errors: list[dict] = Field(default_factory=list)
