import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReportDashboardResponse(BaseModel):
    total_campaigns: int
    active_campaigns: int
    total_sent: int
    total_opened: int
    total_clicked: int
    total_bounced: int
    overall_open_rate: float
    overall_click_rate: float


class CampaignReportResponse(BaseModel):
    campaign_id: uuid.UUID
    report_type: str
    period_start: datetime | None
    period_end: datetime | None
    metrics: dict[str, Any]
    funnel: dict[str, Any] | None
    generated_at: datetime

    model_config = {"from_attributes": True}


class ExportRequest(BaseModel):
    campaign_id: uuid.UUID | None = None
    format: str = "csv"
    date_from: datetime | None = None
    date_to: datetime | None = None
