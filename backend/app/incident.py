import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.incident import IncidentSeverity, IncidentStatus


class IncidentCreate(BaseModel):
    """Manual incident creation. Playbooks create incidents too (via the
    create_incident action in app/services/playbook_engine/actions.py) but
    that path constructs the Incident row directly rather than going through
    this endpoint -- this schema is specifically for an analyst opening an
    incident by hand.
    """

    title: str
    description: Optional[str] = None
    severity: IncidentSeverity = IncidentSeverity.low
    related_alert_id: Optional[uuid.UUID] = None
    assigned_to: Optional[uuid.UUID] = None


class IncidentUpdate(BaseModel):
    """All fields optional -- a PATCH may touch just status, just the
    assignee, or several fields at once. Status transitions are intentionally
    unrestricted (any authorized user can move to any status) to match this
    project's existing preference for simple, auditable logic over a state
    machine; the audit_logs entry written on every status change is what
    keeps that safe rather than a transition allow-list.
    """

    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[IncidentSeverity] = None
    status: Optional[IncidentStatus] = None
    assigned_to: Optional[uuid.UUID] = None


class RelatedAlertSummary(BaseModel):
    """Small nested summary of the linked alert so the frontend can render
    an incident card/detail view without a second round-trip to
    GET /api/v1/alerts/{id}.
    """

    id: uuid.UUID
    alert_type: str
    hostname: Optional[str] = None
    severity: str
    correlation_score: Optional[int] = None
    status: str

    class Config:
        from_attributes = True


class IncidentResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    severity: IncidentSeverity
    status: IncidentStatus
    related_alert_id: Optional[uuid.UUID] = None
    assigned_to: Optional[uuid.UUID] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    related_alert: Optional[RelatedAlertSummary] = None

    class Config:
        from_attributes = True


class IncidentListResponse(BaseModel):
    total: int
    items: list[IncidentResponse]
