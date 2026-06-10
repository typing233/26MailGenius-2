import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TrackingEventResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    campaign_id: uuid.UUID
    subscriber_id: uuid.UUID
    job_id: uuid.UUID | None
    event_type: str
    link_url: str | None
    user_agent: str | None
    is_first: bool
    is_machine: bool
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class BounceWebhookPayload(BaseModel):
    message_id: str | None = None
    email: str
    bounce_type: str = "hard"
    reason: str | None = None
    timestamp: datetime | None = None


class ComplaintWebhookPayload(BaseModel):
    message_id: str | None = None
    email: str
    reason: str | None = None
    timestamp: datetime | None = None
