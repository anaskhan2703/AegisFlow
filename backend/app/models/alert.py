import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.db.base_class import Base


class AlertSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertStatus(str, enum.Enum):
    open = "open"
    investigating = "investigating"
    resolved = "resolved"
    false_positive = "false_positive"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type = Column(String, nullable=False, index=True)
    hostname = Column(String, nullable=True)
    # "user" here is the raw username string tied to the source event,
    # not a FK to the users table (which is for platform accounts).
    user = Column(String, nullable=True)
    details = Column(JSONB, nullable=True)  # command / raw event details
    severity = Column(Enum(AlertSeverity, name="alert_severity"), nullable=False, default=AlertSeverity.low)
    mitre_technique = Column(String, nullable=True)
    status = Column(Enum(AlertStatus, name="alert_status"), nullable=False, default=AlertStatus.open)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
