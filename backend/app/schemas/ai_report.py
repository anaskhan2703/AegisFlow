import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AIReportResponse(BaseModel):
    id: uuid.UUID
    related_alert_id: Optional[uuid.UUID] = None
    summary: Optional[str] = None
    mitre_technique: Optional[str] = None
    recommended_actions: Optional[list[str]] = None
    ai_provider_used: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AIReportListResponse(BaseModel):
    total: int
    items: list[AIReportResponse]
