"""
TriageProvider — common interface for AI-assisted alert triage backends.

Why this exists:
This is the exact same "provider abstraction" pattern used in
threat_intel/base.py — one interface, multiple interchangeable backends,
selected at runtime by a factory based on what's configured. There, it was
VirusTotal/AbuseIPDB/Simulator; here it's Gemini/Simulator. The endpoint,
the DB writer, and anything else calling into this module never needs to
know which backend actually generated a report.

Originally scoped as Ollama (local) + Gemini (fallback), but the project
now uses Gemini only as the real backend, with the simulator standing in
whenever no API key is configured or the Gemini call fails. Keeping the
ABC even with a single real implementation costs little and means adding
a second real provider later (Ollama, Claude, whatever) is a new file, not
a rewrite.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AlertTriageContext:
    """Everything a triage provider needs to reason about an alert.

    Built from the Alert row plus its resolved threat_indicators rows —
    the same indicator_details shape already produced by the correlator
    and by GET /api/v1/alerts/{id}, so no new data-shaping logic is needed
    upstream of this.
    """

    alert_id: str
    alert_type: str
    hostname: Optional[str]
    user: Optional[str]
    severity: str
    mitre_technique: Optional[str]
    status: str
    correlation_score: int
    details: dict[str, Any] = field(default_factory=dict)
    indicator_details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TriageResult:
    """Normalized result every provider must return, regardless of the
    shape of the upstream API response. Maps directly onto the ai_reports
    columns (summary, mitre_technique, recommended_actions, ai_provider_used).
    """

    summary: str
    mitre_technique: Optional[str]
    recommended_actions: list[str]
    provider: str  # "gemini" | "simulated"
    raw: dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None  # 0.0-1.0, how much we trust this verdict


class TriageProviderError(Exception):
    """Raised when a provider fails in a way callers should handle gracefully
    (timeout, rate limit, malformed response) rather than crashing the request."""

    def __init__(self, provider: str, message: str, *, retriable: bool = False):
        self.provider = provider
        self.retriable = retriable
        super().__init__(f"[{provider}] {message}")


class TriageProvider(ABC):
    """Every concrete provider (Gemini, Simulator) implements this
    interface. Callers only ever depend on this base class."""

    name: str = "base"

    @abstractmethod
    async def triage(self, context: AlertTriageContext) -> TriageResult:
        """
        Produce a triage report for a single alert. Implementations must:
          - enforce their own timeout (don't let a slow upstream hang the request)
          - raise TriageProviderError on failure rather than letting
            arbitrary exceptions (httpx errors, KeyErrors on bad JSON) escape
        """
        raise NotImplementedError
