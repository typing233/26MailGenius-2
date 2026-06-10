import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    name: str = Field(max_length=100)
    host: str = Field(max_length=255)
    port: int = 587
    username: str | None = None
    password: str | None = None
    use_tls: bool = True
    is_active: bool = True
    priority: int = 0
    daily_limit: int = 10000
    hourly_limit: int = 1000


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    use_tls: bool | None = None
    is_active: bool | None = None
    priority: int | None = None
    daily_limit: int | None = None
    hourly_limit: int | None = None


class ChannelResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    host: str
    port: int
    username: str | None
    use_tls: bool
    is_active: bool
    priority: int
    daily_limit: int
    hourly_limit: int
    last_success_at: datetime | None
    last_failure_at: datetime | None
    consecutive_failures: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChannelHealthResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    is_healthy: bool
    consecutive_failures: int
    last_success_at: datetime | None
    hourly_remaining: int
    daily_remaining: int


class ChannelTestRequest(BaseModel):
    to_email: str
