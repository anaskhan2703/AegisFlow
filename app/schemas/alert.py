import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.alert import AlertSeverity, AlertStatus


class AlertIngestRequest(BaseModel):
    """Shape matches the real Alert model's fields directly rather than
    a generic title/description/source SIEM shape -- alert_type,
    hostname, user, and details (the raw event/command data) are what
    the app actually stores per-alert.

    `details` is where indicator extraction focuses (it's documented on
    the model as "command / raw event details"), but the whole payload
    is scanned via raw_payload for extraction, so indicators mentioned
    anywhere (e.g. in mitre_technique notes) are still caught.
    """

    alert_type: str = Field(..., examples=["c2_beacon", "brute_force", "port_scan"])
    hostname: Optional[str] = None
    user: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)
    severity: AlertSeverity = AlertSeverity.low
    mitre_technique: Optional[str] = None

    class Config:
        extra = "allow"


class IndicatorDetail(BaseModel):
    indicator: str
    type: str
    severity: str
    reputation: Optional[str] = None
    risk_score: float
    cache_hit: bool


class AlertResponse(BaseModel):
    id: uuid.UUID
    alert_type: str
    hostname: Optional[str] = None
    user: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    severity: AlertSeverity
    mitre_technique: Optional[str] = None
    status: AlertStatus
    raw_payload: dict[str, Any]
    extracted_indicators: list[str]
    correlation_score: int
    created_at: datetime

    class Config:
        from_attributes = True


class AlertResponseWithDetails(AlertResponse):
    indicator_details: list[IndicatorDetail] = Field(default_factory=list)


class AlertStatusUpdate(BaseModel):
    status: AlertStatus


class DemoGenerateRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=50)
    template: Optional[str] = None


class AlertListResponse(BaseModel):
    total: int
    items: list[AlertResponse]
