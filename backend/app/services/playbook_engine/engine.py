"""
Playbook execution engine.

Two entry points:
  - run_playbooks_for_alert: called automatically from the alert
    create/update hooks. Evaluates every active, trigger_type="automatic"
    playbook against the alert and runs the ones whose conditions match.
  - run_single_playbook: called from the manual "run this playbook on this
    alert" endpoint. Always executes (an analyst explicitly asked for it),
    regardless of trigger_type or whether trigger_conditions would have
    matched — conditions still get evaluated and recorded for the audit
    trail, but they don't gate a manual run.

Both funnel through _execute_steps, which is the only place that decides
whether an action actually mutates the DB (auto_executable) or just gets
logged as a recommendation (see actions.py for why that split exists).

Every DB write here happens on the caller's existing session and is NOT
committed by this module — the caller (the alert hook, or the manual-run
endpoint) owns the transaction boundary and commits once, so a playbook
failure can't leave the alert itself half-written.
"""

import logging

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.playbook import Playbook
from app.models.playbook_execution import PlaybookExecution
from app.services.playbook_engine.actions import ACTION_REGISTRY
from app.services.playbook_engine.rules import evaluate_conditions

logger = logging.getLogger(__name__)


def _execute_steps(db: Session, alert: Alert, steps: list[dict] | None) -> tuple[list[dict], str]:
    """Run each step in order. Returns (actions_taken, status).
    Never raises — a bad step is recorded as failed and execution continues
    with the remaining steps, so one malformed action can't silently drop
    the rest of the playbook."""
    if not steps:
        return [], "failed"

    actions_taken = []
    any_executed = False
    any_error = False

    for step in steps:
        action_name = step.get("action")
        params = step.get("params") or {}
        spec = ACTION_REGISTRY.get(action_name)

        if spec is None:
            actions_taken.append(
                {"action": action_name, "params": params, "executed": False, "note": "unknown action name"}
            )
            any_error = True
            continue

        if not spec.auto_executable:
            actions_taken.append(
                {
                    "action": action_name,
                    "params": params,
                    "executed": False,
                    "note": f"recommended, not auto-executed — {spec.description}",
                }
            )
            continue

        try:
            result = spec.handler(db, alert, params)
            actions_taken.append({"action": action_name, "params": params, "executed": True, "result": result})
            any_executed = True
        except Exception as exc:  # noqa: BLE001 — a bad step must not crash the whole run
            logger.warning("Playbook action %s failed on alert %s: %s", action_name, alert.id, exc)
            actions_taken.append(
                {"action": action_name, "params": params, "executed": False, "note": f"error: {exc}"}
            )
            any_error = True

    if any_error and not any_executed:
        status = "failed"
    elif any_error:
        status = "partial"
    else:
        status = "success"

    return actions_taken, status


def run_single_playbook(
    db: Session,
    playbook: Playbook,
    alert: Alert,
    *,
    trigger_source: str,
    executed_by=None,
) -> PlaybookExecution:
    """Execute one playbook against one alert unconditionally (conditions
    are still recorded, not enforced — the caller decides whether to gate
    on them first)."""
    actions_taken, status = _execute_steps(db, alert, playbook.steps)

    execution = PlaybookExecution(
        playbook_id=playbook.id,
        alert_id=alert.id,
        executed_by=executed_by,
        trigger_source=trigger_source,
        status=status,
        triggered_conditions=playbook.trigger_conditions,
        actions_taken=actions_taken,
    )
    db.add(execution)
    db.flush()
    return execution


def run_playbooks_for_alert(db: Session, alert: Alert, *, trigger_source: str = "automatic") -> list[PlaybookExecution]:
    """Evaluate every active, trigger_type='automatic' playbook against this
    alert; run + record the ones whose conditions match. Called from the
    alert ingest and status-update paths. Never raises — a playbook bug
    should never break alert ingestion."""
    executions: list[PlaybookExecution] = []

    playbooks = (
        db.query(Playbook)
        .filter(Playbook.is_active.is_(True))
        .filter(Playbook.trigger_type == "automatic")
        .all()
    )

    for playbook in playbooks:
        try:
            if not evaluate_conditions(playbook.trigger_conditions, alert):
                continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("Condition evaluation failed for playbook %s: %s", playbook.id, exc)
            continue

        try:
            execution = run_single_playbook(db, playbook, alert, trigger_source=trigger_source)
            executions.append(execution)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Playbook %s failed to execute on alert %s: %s", playbook.id, alert.id, exc)

    return executions
