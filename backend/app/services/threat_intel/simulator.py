"""
Simulator provider — generates deterministic, believable-looking threat
intel data without calling any external API.

This is the default provider whenever VIRUSTOTAL_API_KEY / ABUSEIPDB_API_KEY
are blank, which is the default for local/portfolio use. It exists so the
enrichment feature demos convincingly (recruiter clicks "lookup", gets a
real-looking verdict) without requiring anyone to go get free-tier API keys
just to click around the demo.

Determinism matters here: the same indicator should always produce the same
verdict. We do this by hashing the indicator string into a seed rather than
using random.random() — that way "8.8.8.8" always comes back "clean" and
"185.220.101.1" (a real Tor exit node range, used only as a flavor example)
always comes back with a plausible-looking bad verdict, across restarts.
"""

import hashlib

from app.services.threat_intel.base import (
    IndicatorType,
    Severity,
    ThreatIntelProvider,
    ThreatIntelResult,
)

# A small set of indicators we always render as obviously malicious, so demo
# scripts / screenshots have something dramatic to point at.
_KNOWN_BAD_SUBSTRINGS = ("evil", "malware", "phish", "bad-", "botnet")
_KNOWN_GOOD = {"8.8.8.8", "1.1.1.1", "google.com", "cloudflare.com", "github.com"}

_REPUTATION_BY_SEVERITY = {
    Severity.NONE: "clean",
    Severity.LOW: "suspicious",
    Severity.MEDIUM: "likely malicious",
    Severity.HIGH: "malicious",
    Severity.CRITICAL: "confirmed malicious",
}


def _seed(indicator: str) -> int:
    """Stable integer seed derived from the indicator string."""
    digest = hashlib.sha256(indicator.strip().lower().encode()).hexdigest()
    return int(digest[:8], 16)


def _score_to_severity(score: int) -> Severity:
    if score >= 85:
        return Severity.CRITICAL
    if score >= 60:
        return Severity.HIGH
    if score >= 30:
        return Severity.MEDIUM
    if score >= 10:
        return Severity.LOW
    return Severity.NONE


class SimulatorProvider(ThreatIntelProvider):
    name = "simulated"

    async def lookup(self, indicator: str, indicator_type: IndicatorType) -> ThreatIntelResult:
        lowered = indicator.strip().lower()
        seed = _seed(lowered)

        if lowered in _KNOWN_GOOD:
            score = seed % 5  # 0-4, always "none" severity
        elif any(bad in lowered for bad in _KNOWN_BAD_SUBSTRINGS):
            score = 85 + (seed % 16)  # 85-100, always "critical"
        else:
            score = seed % 101  # 0-100, deterministic per-indicator spread

        severity = _score_to_severity(score)
        reputation = _REPUTATION_BY_SEVERITY[severity]

        raw = {
            "engine": "aegisflow-simulator",
            "note": "This result is simulated dummy data — no external API was called.",
            "indicator": indicator,
            "type": indicator_type.value,
            "simulated_score": score,
            "detection_ratio": f"{min(score // 10, 10)}/70",
        }

        return ThreatIntelResult(
            indicator=indicator,
            type=indicator_type,
            risk_score=score,
            severity=severity,
            reputation=reputation,
            source="simulated",
            raw=raw,
            confidence=0.5,  # simulated data is never fully "confident"
        )
