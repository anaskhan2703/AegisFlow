"""
ThreatIntelProvider — common interface for all threat intel sources.

Why this exists:
VirusTotal, AbuseIPDB, and our local simulator all return wildly different
JSON shapes. Every other part of the app (the endpoint, the caching layer,
the DB writer) should not need to know which provider answered — it just
wants a normalized result it can shove into the `threat_indicators` table.

This is the same "provider abstraction" pattern we'll reuse in a later phase
to swap between Ollama and Gemini for AI report generation: one interface,
multiple interchangeable backends, selected at runtime by a factory based on
what's configured.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class IndicatorType(str, Enum):
    IP = "ip"
    DOMAIN = "domain"
    HASH = "hash"
    URL = "url"


class Severity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ThreatIntelResult:
    """
    Normalized result every provider must return, regardless of the
    shape of the upstream API response.
    """
    indicator: str
    type: IndicatorType
    risk_score: int  # 0-100, normalized across all providers
    severity: Severity
    reputation: str  # short human-readable summary, e.g. "malicious", "clean"
    source: str  # "virustotal" | "abuseipdb" | "simulated"
    raw: dict[str, Any] = field(default_factory=dict)  # original payload, stored in sources JSONB
    confidence: Optional[float] = None  # 0.0-1.0, how much we trust this verdict


class ThreatIntelProviderError(Exception):
    """Raised when a provider fails in a way callers should handle gracefully
    (timeout, rate limit, malformed response) rather than crashing the request."""
    def __init__(self, provider: str, message: str, *, retriable: bool = False):
        self.provider = provider
        self.retriable = retriable
        super().__init__(f"[{provider}] {message}")


class ThreatIntelProvider(ABC):
    """
    Every concrete provider (VirusTotal, AbuseIPDB, Simulator) implements
    this interface. Callers only ever depend on this base class, never on
    a concrete provider directly — that's what makes them interchangeable.
    """

    name: str = "base"

    @abstractmethod
    async def lookup(self, indicator: str, indicator_type: IndicatorType) -> ThreatIntelResult:
        """
        Look up a single indicator and return a normalized result.
        Implementations must:
          - enforce their own timeout (don't let a slow upstream hang the request)
          - raise ThreatIntelProviderError on failure rather than letting
            arbitrary exceptions (httpx errors, KeyErrors on bad JSON) escape
        """
        raise NotImplementedError

    def supports(self, indicator_type: IndicatorType) -> bool:
        """Override if a provider can't handle certain indicator types
        (e.g. AbuseIPDB only makes sense for IPs)."""
        return True
