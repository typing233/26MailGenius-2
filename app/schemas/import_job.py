import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ImportJobResponse(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    total_rows: int
    processed_rows: int
    success_rows: int
    error_rows: int
    error_details: list
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportInitiateRequest(BaseModel):
    dedup_key: Optional[str] = None
