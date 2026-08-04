import uuid

from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base_class import Base


class Playbook(Base):
    """
    A Playbook pairs a set of trigger conditions with an ordered list of
    response actions.

    trigger_type: "automatic" (evaluated against every alert create/update)
        or "manual" (only ever runs when an analyst explicitly triggers it
        via POST /playbooks/{id}/run/{alert_id} — useful for playbooks with
        actions too disruptive to fire unattended, e.g. anything touching
        an incident record).

    trigger_conditions: a flat list of rules, ANDed together, e.g.
        [{"field": "correlation_score", "op": ">=", "value": 80},
         {"field": "alert_type", "op": "==", "value": "brute_force"}]
        Deliberately NOT a free-text expression — see
        app/services/playbook_engine/rules.py for why. An empty/null list
        means "always matches" (useful for a manual-only playbook that
        doesn't need a condition at all).

    steps: an ordered list of actions to run when conditions are met, e.g.
        [{"action": "update_alert_status", "params": {"status": "investigating"}},
         {"action": "isolate_host", "params": {}}]
        See app/services/playbook_engine/actions.py for the registry of
        valid action names and which ones actually execute vs. which are
        logged as recommended-but-manual.
    """

    __tablename__ = "playbooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    trigger_type = Column(String, nullable=False, default="automatic")
    trigger_conditions = Column(JSONB, nullable=True)
    steps = Column(JSONB, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
