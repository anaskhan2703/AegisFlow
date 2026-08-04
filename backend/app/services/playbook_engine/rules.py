"""
Trigger condition evaluation for playbooks.

DESIGN NOTE (why this isn't a string expression parser):
A playbook's trigger_conditions field is user-editable data — an analyst (or
eventually a form in the frontend) writes it. The moment user-editable input
is treated as code to execute, you've built an injection vector, even if
today's users are trusted. The classic shortcut here is something like
`eval(condition_string, {"alert": alert})`, which would let a playbook
condition run arbitrary Python.

Instead, a condition is pure data:
    {"field": "correlation_score", "op": ">=", "value": 80}

Evaluating it is a lookup, not a parse-and-execute:
  - `field` must be a key in ALLOWED_FIELDS (a fixed allow-list below) —
    anything else is rejected rather than silently ignored, so a typo'd or
    malicious field name fails loudly instead of matching everything.
  - `op` must be a key in OPERATORS (a fixed dict of comparison functions).
  - `value` is only ever compared against, never executed.

This can't express arbitrary boolean logic (no nested OR/negation) — every
playbook's trigger_conditions is a flat list, ANDed together. That's a
deliberate scope limit, not an oversight: it covers realistic SOC trigger
logic ("high correlation AND this alert type") without the complexity of a
real grammar. It could be extended later with an explicit {"logic": "OR"}
wrapper around sub-lists without needing a rewrite of this module.
"""

import operator
from typing import Any, Callable

from app.models.alert import Alert

# Fixed allow-list: which Alert fields a condition is allowed to read, and
# how to read them. Values are normalized to plain Python primitives (not
# SQLAlchemy Enum members) so comparisons behave predictably.
ALLOWED_FIELDS: dict[str, Callable[[Alert], Any]] = {
    "correlation_score": lambda alert: alert.correlation_score,
    "severity": lambda alert: alert.severity.value if hasattr(alert.severity, "value") else alert.severity,
    "alert_type": lambda alert: alert.alert_type,
    "status": lambda alert: alert.status.value if hasattr(alert.status, "value") else alert.status,
    "mitre_technique": lambda alert: alert.mitre_technique,
    "hostname": lambda alert: alert.hostname,
}

# Fixed set of comparison operators. No arbitrary callables ever get in here.
OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "in": lambda field_value, value: field_value in value if isinstance(value, (list, tuple, set)) else False,
    "contains": lambda field_value, value: value in field_value if isinstance(field_value, str) else False,
}


class InvalidConditionError(Exception):
    """Raised when a condition references an unknown field or operator.
    Callers should treat this as a non-match (and log it), never as a crash
    that takes down alert ingestion."""


def evaluate_condition(condition: dict, alert: Alert) -> bool:
    field = condition.get("field")
    op = condition.get("op")
    value = condition.get("value")

    if field not in ALLOWED_FIELDS:
        raise InvalidConditionError(f"Unknown or disallowed field: {field!r}")
    if op not in OPERATORS:
        raise InvalidConditionError(f"Unknown operator: {op!r}")

    field_value = ALLOWED_FIELDS[field](alert)
    if field_value is None:
        # Missing data never satisfies a condition — avoids surprising
        # matches like None >= 80 raising, or None == None being trivially true
        # for an unrelated field the alert simply didn't populate.
        return False

    try:
        return bool(OPERATORS[op](field_value, value))
    except TypeError:
        # e.g. comparing a string field with ">=" against an int value —
        # a mismatched condition, not a system error.
        return False


def evaluate_conditions(conditions: list[dict] | None, alert: Alert) -> bool:
    """A null/empty condition list always matches (useful for manual-only
    playbooks that don't need a trigger). Otherwise every condition in the
    flat list must pass (AND)."""
    if not conditions:
        return True

    for condition in conditions:
        try:
            if not evaluate_condition(condition, alert):
                return False
        except InvalidConditionError:
            # A malformed condition means the playbook can never validly
            # fire automatically — fail closed (no match) rather than
            # guessing what the author meant.
            return False

    return True
