import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str = Field(max_length=255)
    template_id: uuid.UUID
    sender_name: str | None = None
    sender_email: str | None = None
    reply_to: str | None = None
    list_ids: list[uuid.UUID] = Field(default_factory=list)
    segment_rule_ids: list[uuid.UUID] = Field(default_factory=list)
    exclusion_list_ids: list[uuid.UUID] = Field(default_factory=list)
    scheduled_at: datetime | None = None
    timezone: str = "UTC"
    batch_size: int = 500
    batch_interval_seconds: int = 10
    tags: list[str] = Field(default_factory=list)


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    template_id: uuid.UUID | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    reply_to: str | None = None
    list_ids: list[uuid.UUID] | None = None
    segment_rule_ids: list[uuid.UUID] | None = None
    exclusion_list_ids: list[uuid.UUID] | None = None
    scheduled_at: datetime | None = None
    timezone: str | None = None
    batch_size: int | None = None
    batch_interval_seconds: int | None = None
    tags: list[str] | None = None


class CampaignResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    status: str
    template_id: uuid.UUID
    template_version: int | None
    sender_name: str | None
    sender_email: str | None
    reply_to: str | None
    list_ids: list[uuid.UUID]
    segment_rule_ids: list[uuid.UUID]
    exclusion_list_ids: list[uuid.UUID]
    scheduled_at: datetime | None
    timezone: str
    batch_size: int
    batch_interval_seconds: int
    total_recipients: int
    sent_count: int
    failed_count: int
    opened_count: int
    clicked_count: int
    bounced_count: int
    unsubscribed_count: int
    tags: list[str]
    created_by: uuid.UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    paused_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignProgressResponse(BaseModel):
    campaign_id: uuid.UUID
    status: str
    total_recipients: int
    sent_count: int
    failed_count: int
    progress_pct: float
    estimated_remaining_seconds: int | None


class CampaignStatsResponse(BaseModel):
    campaign_id: uuid.UUID
    total_recipients: int
    sent: int
    delivered: int
    opened: int
    unique_opens: int
    clicked: int
    unique_clicks: int
    bounced: int
    unsubscribed: int
    open_rate: float
    click_rate: float
    bounce_rate: float


class TestSendRequest(BaseModel):
    to_emails: list[str] = Field(min_length=1, max_length=5)
    variables: dict[str, Any] = Field(default_factory=dict)


class ScheduleRequest(BaseModel):
    scheduled_at: datetime
    timezone: str = "UTC"
