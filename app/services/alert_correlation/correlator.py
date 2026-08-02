"""Correlation engine: given a raw alert payload, extract indicators,
resolve each against the threat_indicators cache (or a fresh Phase 3
lookup if not cached/stale), and aggregate a single alert-level
correlation_score.

Notes on matching the real Phase 3 shape (this bit us once already
during handoff, documented here so the next phase doesn't repeat it):

- `lookup_indicator()` is ASYNC and takes an `IndicatorType` enum, not a
  plain string. This function is therefore async too, and awaits it.
- `ThreatIndicator` has no update/last-checked timestamp column, only
  `created_at`. So there's no "refresh this row in place" -- instead,
  each fresh lookup INSERTS a new row (append-only history), and the
  cache check just looks at the most recent row by `created_at`. This
  also means threat_indicators naturally accumulates a lookup history
  per indicator over time, which is a nice side benefit for an audit
  trail even though it wasn't the original goal.
- `ThreatIndicator.risk_score` is a nullable Float (provider-normalized
  0-100, but not guaranteed present) and `severity`/`reputation` are
  free-text strings, not enums, since the provider abstraction's
  `ThreatIntelResult.severity` (a `Severity` enum) and `.reputation`
  (a short string) get stored as `.value` / plain string.
- The full `ThreatIntelResult` (source, raw, confidence) is folded into
  the single `sources` JSONB column, since that's the only slot
  available for provider detail on this model.

Known limitation, called out rather than hidden: this function mixes a
sync SQLAlchemy Session with an awaited async network call
(`lookup_indicator`). That means the sync DB calls block the event loop
for their duration -- acceptable at this project's scale (a portfolio
demo, not a high-throughput SOC), but worth naming explicitly if this
comes up in an interview: the "correct" production fix would be either
an async DB driver end-to-end, or offloading the sync DB calls to a
thread via `run_in_threadpool`/`asyncio.to_thread`.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.threat_indicator import ThreatIndicator
from app.models.threat_indicator import IndicatorType as ModelIndicatorType
from app.services.threat_intel import lookup_indicator
from app.services.threat_intel.base import IndicatorType, Severity
from app.services.alert_correlation.extractor import extract_indicators

CACHE_WINDOW = timedelta(hours=24)

SEVERITY_WEIGHT = {
    Severity.CRITICAL.value: 4,
    Severity.HIGH.value: 3,
    Severity.MEDIUM.value: 2,
    Severity.LOW.value: 1,
    Severity.NONE.value: 1,
}

# Indicators at or above this severity count toward the "multiple bad
# indicators" bonus below.
BONUS_SEVERITIES = {Severity.HIGH.value, Severity.CRITICAL.value}


async def _get_or_lookup(db: Session, indicator: str, indicator_type_str: str) -> tuple[ThreatIndicator, bool]:
    """Return (ThreatIndicator row, was_cache_hit)."""
    cutoff = datetime.now(timezone.utc) - CACHE_WINDOW
    model_type = ModelIndicatorType(indicator_type_str)

    existing = (
        db.query(ThreatIndicator)
        .filter(ThreatIndicator.indicator == indicator, ThreatIndicator.type == model_type)
        .order_by(ThreatIndicator.created_at.desc())
        .first()
    )

    if existing is not None:
        created_at = existing.created_at
        if created_at is not None and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at is not None and created_at >= cutoff:
            return existing, True

    # No cached/recent result -- call into the Phase 3 enrichment pipeline.
    result = await lookup_indicator(indicator, IndicatorType(indicator_type_str))

    row = ThreatIndicator(
        indicator=result.indicator,
        type=model_type,
        risk_score=result.risk_score,
        severity=result.severity.value if hasattr(result.severity, "value") else result.severity,
        reputation=result.reputation,
        sources={
            "source": result.source,
            "raw": result.raw,
            "confidence": result.confidence,
        },
    )
    db.add(row)
    db.flush()  # populate row.id / created_at without committing yet
    return row, False


async def correlate_alert(db: Session, raw_payload: dict) -> dict:
    """Extract indicators from raw_payload, resolve each one (cache or
    fresh async lookup), and compute the aggregate correlation_score.

    Returns:
        {
            "extracted_indicators": [str, ...],
            "correlation_score": int,
            "indicator_details": [
                {"indicator", "type", "severity", "reputation", "risk_score", "cache_hit"},
                ...
            ],
        }
    Caller is responsible for committing the session.
    """
    candidates = extract_indicators(raw_payload)

    if not candidates:
        return {"extracted_indicators": [], "correlation_score": 0, "indicator_details": []}

    details = []
    weighted_sum = 0.0
    weight_total = 0.0
    bonus_count = 0

    for c in candidates:
        row, cache_hit = await _get_or_lookup(db, c["indicator"], c["type"])
        severity_value = row.severity or Severity.NONE.value
        weight = SEVERITY_WEIGHT.get(severity_value, 1)
        score = row.risk_score if row.risk_score is not None else 0
        weighted_sum += score * weight
        weight_total += weight
        if severity_value in BONUS_SEVERITIES:
            bonus_count += 1

        details.append(
            {
                "indicator": row.indicator,
                "type": row.type.value if hasattr(row.type, "value") else row.type,
                "severity": severity_value,
                "reputation": row.reputation,
                "risk_score": score,
                "cache_hit": cache_hit,
            }
        )

    base_score = weighted_sum / weight_total if weight_total else 0
    bonus = max(0, bonus_count - 1) * 5
    correlation_score = min(100, round(base_score + bonus))

    return {
        "extracted_indicators": [d["indicator"] for d in details],
        "correlation_score": correlation_score,
        "indicator_details": details,
    }
