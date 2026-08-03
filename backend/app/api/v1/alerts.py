from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user, require_role
from app.db.session import get_db
from app.models.alert import Alert, AlertStatus
from app.models.user import User
from app.schemas.alert import (
    AlertIngestRequest,
    AlertListResponse,
    AlertResponse,
    AlertResponseWithDetails,
    AlertStatusUpdate,
    DemoGenerateRequest,
)
from app.services.alert_correlation.correlator import correlate_alert
from app.services.alert_correlation.demo_generator import generate_demo_alerts

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


async def _ingest_one(db: Session, payload: dict) -> Alert:
    """Shared ingestion path used by both /ingest and /generate-demo."""
    correlation = await correlate_alert(db, payload)

    alert = Alert(
        alert_type=payload.get("alert_type", "unknown"),
        hostname=payload.get("hostname"),
        user=payload.get("user"),
        details=payload.get("details", {}),
        severity=payload.get("severity", "low"),
        mitre_technique=payload.get("mitre_technique"),
        raw_payload=payload,
        extracted_indicators=correlation["extracted_indicators"],
        correlation_score=correlation["correlation_score"],
        status=AlertStatus.open,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    alert._indicator_details = correlation["indicator_details"]
    return alert


@router.post(
    "/ingest",
    response_model=AlertResponseWithDetails,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_alert(
    payload: AlertIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "soc_analyst")),
):
    """Accept a raw alert payload, extract + correlate indicators against
    threat intel (cache or fresh Phase 3 lookup), store and return the
    enriched alert.
    """
    raw = payload.model_dump(mode="json")
    alert = await _ingest_one(db, raw)
    response = AlertResponseWithDetails.model_validate(alert)
    response.indicator_details = alert._indicator_details
    return response


@router.post(
    "/generate-demo",
    response_model=list[AlertResponse],
    status_code=status.HTTP_201_CREATED,
)
async def generate_demo(
    body: DemoGenerateRequest = DemoGenerateRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "soc_analyst")),
):
    """Generate and ingest N realistic simulated alerts for demo/portfolio
    purposes, running them through the same correlation pipeline as
    real ingested alerts.
    """
    try:
        payloads = generate_demo_alerts(count=body.count, template=body.template)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    alerts = []
    for p in payloads:
        alerts.append(await _ingest_one(db, p))
    return alerts


@router.get("/{alert_id}", response_model=AlertResponseWithDetails)
def get_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    from app.models.threat_indicator import ThreatIndicator

    details = []
    if alert.extracted_indicators:
        rows = (
            db.query(ThreatIndicator)
            .filter(ThreatIndicator.indicator.in_(alert.extracted_indicators))
            .order_by(ThreatIndicator.created_at.desc())
            .all()
        )
        seen = set()
        for row in rows:
            if row.indicator in seen:
                continue
            seen.add(row.indicator)
            details.append(
                {
                    "indicator": row.indicator,
                    "type": row.type.value if hasattr(row.type, "value") else row.type,
                    "severity": row.severity,
                    "reputation": row.reputation,
                    "risk_score": row.risk_score if row.risk_score is not None else 0,
                    "cache_hit": True,
                }
            )

    response = AlertResponseWithDetails.model_validate(alert)
    response.indicator_details = details
    return response


@router.get("/", response_model=AlertListResponse)
def list_alerts(
    status_filter: Optional[AlertStatus] = Query(default=None, alias="status"),
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Alert)
    if status_filter is not None:
        query = query.filter(Alert.status == status_filter)
    if min_score is not None:
        query = query.filter(Alert.correlation_score >= min_score)

    total = query.count()
    items = (
        query.order_by(Alert.created_at.desc()).offset(skip).limit(limit).all()
    )
    return AlertListResponse(total=total, items=items)


@router.patch("/{alert_id}/status", response_model=AlertResponse)
def update_alert_status(
    alert_id: str,
    body: AlertStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "soc_analyst")),
):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.status = body.status
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
