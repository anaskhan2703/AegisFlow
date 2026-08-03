"""
AI Report endpoints.

POST   /api/v1/ai-reports/generate/{alert_id}  -> run AI triage on an alert, store + return the report
GET    /api/v1/ai-reports/{report_id}          -> fetch a previously generated report
GET    /api/v1/ai-reports/                     -> list/paginate reports, optionally filtered by alert_id
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user, require_role
from app.db.session import get_db
from app.models.ai_report import AIReport
from app.models.alert import Alert
from app.models.threat_indicator import ThreatIndicator
from app.models.user import User
from app.schemas.ai_report import AIReportListResponse, AIReportResponse
from app.services.ai_triage import AlertTriageContext, generate_triage_report

router = APIRouter(prefix="/api/v1/ai-reports", tags=["ai-reports"])


def _indicator_details_for_alert(db: Session, alert: Alert) -> list[dict]:
    """Same lookup pattern used in GET /api/v1/alerts/{id}: pull the most
    recent threat_indicators row for each indicator already extracted and
    stored on the alert (no fresh network lookups here — correlation
    already resolved these at ingest time)."""
    if not alert.extracted_indicators:
        return []

    rows = (
        db.query(ThreatIndicator)
        .filter(ThreatIndicator.indicator.in_(alert.extracted_indicators))
        .order_by(ThreatIndicator.created_at.desc())
        .all()
    )
    seen = set()
    details = []
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
            }
        )
    return details


@router.post(
    "/generate/{alert_id}",
    response_model=AIReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_report(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "soc_analyst")),
):
    """Run AI-assisted triage on an alert (Gemini, falling back to the
    rule-based simulator) and persist the result as a new ai_reports row.

    Each call creates a new report rather than updating in place, so
    ai_reports naturally accumulates a triage history per alert — useful
    if the alert's correlation/status changes and it's re-triaged later.
    """
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    context = AlertTriageContext(
        alert_id=str(alert.id),
        alert_type=alert.alert_type,
        hostname=alert.hostname,
        user=alert.user,
        severity=alert.severity.value if hasattr(alert.severity, "value") else alert.severity,
        mitre_technique=alert.mitre_technique,
        status=alert.status.value if hasattr(alert.status, "value") else alert.status,
        correlation_score=alert.correlation_score,
        details=alert.details or {},
        indicator_details=_indicator_details_for_alert(db, alert),
    )

    result = await generate_triage_report(context)

    report = AIReport(
        related_alert_id=alert.id,
        summary=result.summary,
        mitre_technique=result.mitre_technique,
        recommended_actions=result.recommended_actions,
        ai_provider_used=result.provider,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/{report_id}", response_model=AIReportResponse)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.get(AIReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI report not found")
    return report


@router.get("/", response_model=AIReportListResponse)
def list_reports(
    alert_id: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AIReport)
    if alert_id is not None:
        query = query.filter(AIReport.related_alert_id == alert_id)

    total = query.count()
    items = query.order_by(AIReport.created_at.desc()).offset(skip).limit(limit).all()
    return AIReportListResponse(total=total, items=items)
