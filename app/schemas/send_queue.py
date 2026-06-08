import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SendQueueJobCreate(BaseModel):
    campaign_id: Optional[uuid.UUID] = None
    subscriber_id: uuid.UUID
    list_id: Optional[uuid.UUID] = None
    scheduled_at: Optional[datetime] = None


class SendQueueJobResponse(BaseModel):
    id: uuid.UUID
    campaign_id: Optional[uuid.UUID]
    subscriber_id: uuid.UUID
    list_id: Optional[uuid.UUID]
    status: str
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    failed_at: Optional[datetime]
    error_message: Optional[str]
    retry_count: int
    max_retries: int
    created_at: datetime

    model_config = {"from_attributes": True}
