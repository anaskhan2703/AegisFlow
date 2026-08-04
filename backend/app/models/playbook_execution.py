import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.db.base_class import Base


class PlaybookExecution(Base):
    """
    One row per playbook run against one alert — the audit trail the old
    `playbooks` table had no way to record. A single alert create/update can
    fan out into multiple PlaybookExecution rows (one per matching active
    playbook), and a single manual run produces exactly one.

    Nothing here is a live pointer to "current" playbook/alert state — both
    trigger_conditions and actions_taken are snapshots captured at run time,
    so the audit trail stays accurate even if the playbook definition or the
    alert is edited later.
    """

    __tablename__ = "playbook_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    playbook_id = Column(
        UUID(as_uuid=True), ForeignKey("playbooks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    alert_id = Column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    executed_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # "automatic" (fired from the alert create/update hook) or "manual"
    # (an analyst hit the run endpoint directly).
    trigger_source = Column(String, nullable=False)

    # "success" (every action executed or was cleanly logged as manual-only),
    # "partial" (at least one action raised but others completed), or
    # "failed" (nothing executed, e.g. the playbook had no valid steps).
    status = Column(String, nullable=False)

    # Snapshot of the conditions that were evaluated for this run, so the
    # record stays meaningful even if the playbook is edited afterward.
    triggered_conditions = Column(JSONB, nullable=True)

    # Ordered list of {action, params, executed, note} — see
    # app/services/playbook_engine/engine.py for the exact shape.
    actions_taken = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
