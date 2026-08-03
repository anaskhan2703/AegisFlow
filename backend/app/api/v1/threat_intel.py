"""
Threat Intelligence endpoints.

POST   /api/v1/threat-intel/lookup     -> enrich an indicator (cache-first)
GET    /api/v1/threat-intel/{indicator}-> fetch a previously stored indicator
GET    /api/v1/threat-intel/           -> list/paginate stored indicators
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user, require_role
from app.db.session import get_db
from app.models.threat_indicator import ThreatIndicator
from app.models.user import User
from app.schemas.threat_intel import (
    ThreatIndicatorFilterParams,
    ThreatIndicatorListResponse,
    ThreatIndicatorResponse,
    ThreatIntelLookupRequest,
)
from app.services.threat_intel import IndicatorType, lookup_indicator

router = APIRouter(prefix="/api/v1/threat-intel", tags=["threat-intel"])

# How long a stored indicator is considered "fresh" before we re-query it.
# This is the caching optimization called out in the phase spec: cheap to
# raise/lower for demo purposes, and worth citing explicitly as a deliberate
# rate-limit/cost control when explaining this design in an interview.
CACHE_WINDOW = timedelta(hours=24)


def _get_recent_cached(db: Session, indicator: str) -> ThreatIndicator | None:
    cutoff = datetime.now(timezone.utc) - CACHE_WINDOW
    result = db.execute(
        select(ThreatIndicator)
        .where(ThreatIndicator.indicator == indicator)
        .where(ThreatIndicator.created_at >= cutoff)
        .order_by(ThreatIndicator.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post(
    "/lookup",
    response_model=ThreatIndicatorResponse,
    status_code=status.HTTP_200_OK,
)
async def lookup(
    payload: ThreatIntelLookupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "soc_analyst")),
):
    """
    Enrich an indicator. Checks the cache first (any entry for this exact
    indicator string created within CACHE_WINDOW); if none exists, queries
    the configured provider (real if API keys are set, simulated otherwise),
    stores the result, and returns it.

    Note: the DB calls in this endpoint are synchronous (this app's session
    is a plain SQLAlchemy Session, not an async one) but the provider lookup
    itself (lookup_indicator) is genuinely async — it awaits httpx calls out
    to VirusTotal/AbuseIPDB. Mixing the two is fine: FastAPI runs sync-style
    ORM calls in this coroutine without blocking the event loop for long,
    and the only real "await" here is the actual network call.
    """
    cached = _get_recent_cached(db, payload.indicator)
    if cached is not None:
        response = ThreatIndicatorResponse.model_validate(cached)
        response.cached = True
        return response

    result = await lookup_indicator(payload.indicator, payload.type)

    existing = db.execute(
        select(ThreatIndicator).where(ThreatIndicator.indicator == payload.indicator)
    )
    row = existing.scalar_one_or_none()

    if row is None:
        row = ThreatIndicator(
            indicator=result.indicator,
            type=result.type.value,
            risk_score=result.risk_score,
            severity=result.severity.value,
            reputation=result.reputation,
            sources={result.source: result.raw},
        )
        db.add(row)
    else:
        # Update in place and merge the new source's raw payload in rather
        # than clobbering history from other providers.
        row.risk_score = result.risk_score
        row.severity = result.severity.value
        row.reputation = result.reputation
        merged_sources = dict(row.sources or {})
        merged_sources[result.source] = result.raw
        row.sources = merged_sources
        if hasattr(row, "updated_at"):
            row.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(row)

    response = ThreatIndicatorResponse.model_validate(row)
    response.cached = False
    return response


@router.get("/", response_model=ThreatIndicatorListResponse)
async def list_indicators(
    filters: ThreatIndicatorFilterParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List/paginate stored indicators, optionally filtered by type or severity."""
    query = select(ThreatIndicator)
    count_query = select(func.count()).select_from(ThreatIndicator)

    if filters.type is not None:
        query = query.where(ThreatIndicator.type == filters.type.value)
        count_query = count_query.where(ThreatIndicator.type == filters.type.value)

    if filters.severity is not None:
        query = query.where(ThreatIndicator.severity == filters.severity.value)
        count_query = count_query.where(ThreatIndicator.severity == filters.severity.value)

    total = db.execute(count_query).scalar_one()

    query = (
        query.order_by(ThreatIndicator.created_at.desc())
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    )
    rows = db.execute(query).scalars().all()

    return ThreatIndicatorListResponse(
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        items=[ThreatIndicatorResponse.model_validate(r) for r in rows],
    )


@router.get("/{indicator}", response_model=ThreatIndicatorResponse)
async def get_indicator(
    indicator: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch a previously stored indicator by its exact value."""
    result = db.execute(
        select(ThreatIndicator)
        .where(ThreatIndicator.indicator == indicator)
        .order_by(ThreatIndicator.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Indicator not found")

    return ThreatIndicatorResponse.model_validate(row)
