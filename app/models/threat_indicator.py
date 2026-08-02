import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, Float, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.db.base_class import Base


class IndicatorType(str, enum.Enum):
    ip = "ip"
    domain = "domain"
    hash = "hash"
    url = "url"


class ThreatIndicator(Base):
    __tablename__ = "threat_indicators"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    indicator = Column(String, nullable=False, index=True)
    type = Column(Enum(IndicatorType, name="indicator_type"), nullable=False)
    risk_score = Column(Float, nullable=True)
    severity = Column(String, nullable=True)
    reputation = Column(String, nullable=True)
    sources = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
