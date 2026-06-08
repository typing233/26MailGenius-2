import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EmbedFormConfigCreate(BaseModel):
    list_id: uuid.UUID
    allowed_domains: list[str] = Field(default_factory=list)
    honeypot_field_name: str = "website"
    captcha_enabled: bool = False
    captcha_provider: Optional[str] = None
    captcha_site_key: Optional[str] = None
    captcha_secret_key: Optional[str] = None
    rate_limit_per_ip: int = 5
    custom_css: Optional[str] = None
    redirect_url: Optional[str] = None


class EmbedFormConfigResponse(BaseModel):
    id: uuid.UUID
    list_id: uuid.UUID
    allowed_domains: list[str]
    honeypot_field_name: str
    captcha_enabled: bool
    rate_limit_per_ip: int
    created_at: datetime

    model_config = {"from_attributes": True}


class EmbedCodeResponse(BaseModel):
    html: str
    config_id: uuid.UUID
