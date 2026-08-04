"""
Playbook action registry.

Every action a playbook step can name lives in ACTION_REGISTRY. Each entry
is either:

  - auto_executable=True, with a handler that actually mutates the DB
    (update a status, flag an indicator, open an incident, log a
    simulated notification). These are safe to run unattended because
    everything they touch is data already inside AegisFlow.

  - auto_executable=False, handler=None. These name things a *real* SOAR
    platform would do through EDR/firewall/IdP integrations this project
    doesn't have (isolate a host, disable an account, block an IP). The
    engine never calls anything for these — it records them in
    actions_taken as "recommended, not executed" regardless of whether the
    playbook run was automatic or an analyst manually triggered it. There's
    no real endpoint to call, so "executing" one would just be theater;
    logging it as a recommendation is the honest simulation.

This split — not "auto actions only run automatically, manual actions only
run when a human triggers them" — is intentional. See PROGRESS.md's Phase 6
kickoff notes: whether an action executes depends on whether AegisFlow has
somewhere real to send it, not on how the playbook itself was triggered.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertStatus
from app.models.incident import Incident, IncidentSeverity
from app.models.threat_indicator import ThreatIndicator


@dataclass
class ActionSpec:
    auto_executable: bool
    handler: Optional[Callable[[Session, Alert, dict], dict]]
    description: str


def _update_alert_status(db: Session, alert: Alert, params: dict) -> dict:
    new_status = params.get("status")
    valid_values = {s.value for s in AlertStatus}
    if new_status not in valid_values:
        raise ValueError(f"'{new_status}' is not a valid alert status (expected one of {sorted(valid_values)})")
    old_status = alert.status.value if hasattr(alert.status, "value") else alert.status
    alert.status = AlertStatus(new_status)
    db.add(alert)
    return {"old_status": old_status, "new_status": new_status}


def _flag_indicator(db: Session, alert: Alert, params: dict) -> dict:
    if not alert.extracted_indicators:
        return {"flagged": [], "note": "alert has no extracted_indicators to flag"}

    rows = (
        db.query(ThreatIndicator)
        .filter(ThreatIndicator.indicator.in_(alert.extracted_indicators))
        .all()
    )
    flagged = []
    for row in rows:
        row.severity = "critical"
        sources = dict(row.sources) if row.sources else {}
        flags = list(sources.get("playbook_flags", []))
        flags.append(
            {
                "alert_id": str(alert.id),
                "flagged_at": datetime.now(timezone.utc).isoformat(),
                "reason": params.get("reason", "flagged by playbook"),
            }
        )
        sources["playbook_flags"] = flags
        row.sources = sources
        db.add(row)
        flagged.append(row.indicator)

    return {"flagged": flagged}


def _create_incident(db: Session, alert: Alert, params: dict) -> dict:
    severity_str = params.get("severity") or (
        alert.severity.value if hasattr(alert.severity, "value") else alert.severity
    )
    valid_values = {s.value for s in IncidentSeverity}
    if severity_str not in valid_values:
        severity_str = "medium"

    title = params.get("title") or f"{alert.alert_type} on {alert.hostname or 'unknown host'}"
    incident = Incident(
        title=title,
        description=params.get(
            "description", f"Auto-created by playbook from alert {alert.id} (correlation_score={alert.correlation_score})."
        ),
        severity=IncidentSeverity(severity_str),
        related_alert_id=alert.id,
    )
    db.add(incident)
    db.flush()  # populate incident.id without a full commit
    return {"incident_id": str(incident.id), "title": title, "severity": severity_str}


def _notify_analyst(db: Session, alert: Alert, params: dict) -> dict:
    # No real notification integration (email/Slack/PagerDuty) exists in
    # this project — this simulates the "notify" step by producing a
    # message that gets recorded in actions_taken, same as a real
    # integration's send-confirmation would.
    message = params.get(
        "message", f"SOC notified: {alert.alert_type} alert on {alert.hostname or 'unknown host'} requires review."
    )
    return {"message": message, "note": "simulated — no real notification channel configured"}


ACTION_REGISTRY: dict[str, ActionSpec] = {
    "update_alert_status": ActionSpec(
        auto_executable=True,
        handler=_update_alert_status,
        description="Change the alert's status (e.g. open -> investigating).",
    ),
    "flag_indicator": ActionSpec(
        auto_executable=True,
        handler=_flag_indicator,
        description="Elevate severity on the alert's threat_indicators rows and note why.",
    ),
    "create_incident": ActionSpec(
        auto_executable=True,
        handler=_create_incident,
        description="Open an Incident record linked to this alert.",
    ),
    "notify_analyst": ActionSpec(
        auto_executable=True,
        handler=_notify_analyst,
        description="Simulate notifying the SOC (no real channel wired up).",
    ),
    "isolate_host": ActionSpec(
        auto_executable=False,
        handler=None,
        description="Would isolate the host via EDR — requires real EDR integration, not present in this project.",
    ),
    "disable_account": ActionSpec(
        auto_executable=False,
        handler=None,
        description="Would disable the user's account via IdP — requires real IdP integration.",
    ),
    "block_ip": ActionSpec(
        auto_executable=False,
        handler=None,
        description="Would push a block rule to the firewall — requires real firewall integration.",
    ),
}


def known_action_names() -> list[str]:
    return sorted(ACTION_REGISTRY.keys())
