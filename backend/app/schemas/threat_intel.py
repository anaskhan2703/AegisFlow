from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.services.threat_intel.base import IndicatorType, Severity


class ThreatIntelLookupRequest(BaseModel):
    indicator: str = Field(..., min_length=1, max_length=512, examples=["8.8.8.8"])
    type: IndicatorType

    @field_validator("indicator")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("indicator must not be blank")
        return v


class ThreatIndicatorResponse(BaseModel):
    id: UUID
    indicator: str
    type: str
    risk_score: int
    severity: str
    reputation: str
    sources: dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None
    cached: bool = Field(
        default=False,
        description="True if this result was served from a recent cached entry rather than a fresh lookup.",
    )

    model_config = {"from_attributes": True}


class ThreatIndicatorListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ThreatIndicatorResponse]


class ThreatIndicatorFilterParams(BaseModel):
    type: Optional[IndicatorType] = None
    severity: Optional[Severity] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
