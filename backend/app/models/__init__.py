"""
Import every model here so that:
1. `Base.metadata` is fully populated (Alembic autogenerate relies on this).
2. Application code can do `from app.models import User, Alert, ...`.
"""
from app.models.user import User, UserRole  # noqa: F401
from app.models.alert import Alert, AlertSeverity, AlertStatus  # noqa: F401
from app.models.threat_indicator import ThreatIndicator, IndicatorType  # noqa: F401
from app.models.risk_score import RiskScore  # noqa: F401
from app.models.ai_report import AIReport  # noqa: F401
from app.models.playbook import Playbook  # noqa: F401
from app.models.playbook_execution import PlaybookExecution  # noqa: F401
from app.models.incident import Incident, IncidentSeverity, IncidentStatus  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
