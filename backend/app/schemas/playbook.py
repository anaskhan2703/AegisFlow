import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PlaybookCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str = Field(default="automatic", pattern="^(automatic|manual)$")
    trigger_conditions: Optional[list[dict[str, Any]]] = None
    steps: list[dict[str, Any]]
    is_active: bool = True


class PlaybookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = Field(default=None, pattern="^(automatic|manual)$")
    trigger_conditions: Optional[list[dict[str, Any]]] = None
    steps: Optional[list[dict[str, Any]]] = None
    is_active: Optional[bool] = None


class PlaybookResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_conditions: Optional[list[dict[str, Any]]] = None
    steps: Optional[list[dict[str, Any]]] = None
    is_active: bool

    class Config:
        from_attributes = True


class PlaybookListResponse(BaseModel):
    total: int
    items: list[PlaybookResponse]


class PlaybookExecutionResponse(BaseModel):
    id: uuid.UUID
    playbook_id: Optional[uuid.UUID] = None
    alert_id: Optional[uuid.UUID] = None
    executed_by: Optional[uuid.UUID] = None
    trigger_source: str
    status: str
    triggered_conditions: Optional[list[dict[str, Any]]] = None
    actions_taken: Optional[list[dict[str, Any]]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PlaybookExecutionListResponse(BaseModel):
    total: int
    items: list[PlaybookExecutionResponse]
