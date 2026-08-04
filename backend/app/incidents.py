from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.core.rbac import get_current_user, require_role
from app.db.session import get_db
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.user import User
from app.schemas.incident import (
    IncidentCreate,
    IncidentListResponse,
    IncidentResponse,
    IncidentUpdate,
    RelatedAlertSummary,
)

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

# Statuses that mean "work on this incident is done" -- used to decide
# whether resolved_at should be stamped or cleared on a status change.
_CLOSED_STATUSES = {IncidentStatus.resolved, IncidentStatus.closed}


def _to_response(incident: Incident) -> IncidentResponse:
    """Attach the related alert summary (if any) before serializing.
    Done manually rather than via a SQLAlchemy relationship() because none
    of the other models in this project use ORM relationships either --
    every cross-model lookup so far (see api/v1/alerts.py's ThreatIndicator
    join) is an explicit query, and staying consistent with that pattern
    matters more here than the small convenience a relationship would add.
    """
    response = IncidentResponse.model_validate(incident)
    if incident.related_alert_id and getattr(incident, "_related_alert", None) is not None:
        response.related_alert = RelatedAlertSummary.model_validate(incident._related_alert)
    return response


@router.post("/", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "soc_analyst")),
):
    """Manually open an incident. Distinct from the automatic path where a
    playbook's create_incident action opens one during alert correlation --
    this is for an analyst who spots something that doesn't (or shouldn't)
    go through a playbook.
    """
    related_alert = None
    if payload.related_alert_id is not None:
        related_alert = db.get(Alert, payload.related_alert_id)
        if related_alert is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="related_alert_id does not match an existing alert")

    if payload.assigned_to is not None:
        assignee = db.get(User, payload.assigned_to)
        if assignee is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="assigned_to does not match an existing user")

    incident = Incident(
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        status=IncidentStatus.open,
        related_alert_id=payload.related_alert_id,
        assigned_to=payload.assigned_to,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="incident_created",
            resource_type="incident",
            resource_id=str(incident.id),
            details={"title": incident.title, "severity": incident.severity.value},
        )
    )
    db.commit()

    incident._related_alert = related_alert
    return _to_response(incident)


@router.get("/", response_model=IncidentListResponse)
def list_incidents(
    status_filter: Optional[IncidentStatus] = Query(default=None, alias="status"),
    severity_filter: Optional[IncidentSeverity] = Query(default=None, alias="severity"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Incident)
    if status_filter is not None:
        query = query.filter(Incident.status == status_filter)
    if severity_filter is not None:
        query = query.filter(Incident.severity == severity_filter)

    total = query.count()
    items = query.order_by(Incident.created_at.desc()).offset(skip).limit(limit).all()

    # Batch-fetch related alerts in one query rather than N+1.
    alert_ids = [i.related_alert_id for i in items if i.related_alert_id is not None]
    alerts_by_id = {}
    if alert_ids:
        for a in db.query(Alert).filter(Alert.id.in_(alert_ids)).all():
            alerts_by_id[a.id] = a
    for i in items:
        i._related_alert = alerts_by_id.get(i.related_alert_id)

    return IncidentListResponse(total=total, items=[_to_response(i) for i in items])


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    related_alert = None
    if incident.related_alert_id is not None:
        related_alert = db.get(Alert, incident.related_alert_id)
    incident._related_alert = related_alert

    return _to_response(incident)


@router.patch("/{incident_id}", response_model=IncidentResponse)
def update_incident(
    incident_id: str,
    body: IncidentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "soc_analyst")),
):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    if body.assigned_to is not None:
        assignee = db.get(User, body.assigned_to)
        if assignee is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="assigned_to does not match an existing user")

    previous_status = incident.status
    update_data = body.model_dump(exclude_unset=True)

    for field in ("title", "description", "severity", "assigned_to"):
        if field in update_data:
            setattr(incident, field, update_data[field])

    status_changed = "status" in update_data and update_data["status"] != previous_status
    if status_changed:
        incident.status = update_data["status"]
        if incident.status in _CLOSED_STATUSES:
            incident.resolved_at = func.now()
        else:
            incident.resolved_at = None

    db.add(incident)
    db.commit()
    db.refresh(incident)

    if status_changed:
        db.add(
            AuditLog(
                user_id=current_user.id,
                action="incident_status_change",
                resource_type="incident",
                resource_id=str(incident.id),
                details={
                    "from": previous_status.value,
                    "to": incident.status.value,
                },
            )
        )
        db.commit()

    incident._related_alert = (
        db.get(Alert, incident.related_alert_id) if incident.related_alert_id else None
    )
    return _to_response(incident)
