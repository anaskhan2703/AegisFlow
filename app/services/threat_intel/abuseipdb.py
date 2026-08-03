"""
AbuseIPDB provider (free tier).

Docs: https://docs.abuseipdb.com/
Only meaningful for IP indicators — reports an "abuse confidence score"
(0-100) based on community-submitted abuse reports. Free tier is limited to
1,000 checks/day.
"""

import httpx

from app.core.config import settings
from app.services.threat_intel.base import (
    IndicatorType,
    Severity,
    ThreatIntelProvider,
    ThreatIntelProviderError,
    ThreatIntelResult,
)

_URL = "https://api.abuseipdb.com/api/v2/check"
_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


def _severity_from_confidence(score: int) -> Severity:
    if score >= 90:
        return Severity.CRITICAL
    if score >= 60:
        return Severity.HIGH
    if score >= 25:
        return Severity.MEDIUM
    if score > 0:
        return Severity.LOW
    return Severity.NONE


class AbuseIPDBProvider(ThreatIntelProvider):
    name = "abuseipdb"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.ABUSEIPDB_API_KEY

    def supports(self, indicator_type: IndicatorType) -> bool:
        return indicator_type == IndicatorType.IP

    async def lookup(self, indicator: str, indicator_type: IndicatorType) -> ThreatIntelResult:
        if not self.api_key:
            raise ThreatIntelProviderError(self.name, "no API key configured")
        if not self.supports(indicator_type):
            raise ThreatIntelProviderError(self.name, f"unsupported indicator type: {indicator_type}")

        headers = {"Key": self.api_key, "Accept": "application/json"}
        params = {"ipAddress": indicator, "maxAgeInDays": "90", "verbose": "true"}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(_URL, headers=headers, params=params)
        except httpx.TimeoutException as exc:
            raise ThreatIntelProviderError(self.name, "request timed out", retriable=True) from exc
        except httpx.RequestError as exc:
            raise ThreatIntelProviderError(self.name, f"request failed: {exc}", retriable=True) from exc

        if response.status_code == 429:
            raise ThreatIntelProviderError(self.name, "rate limited", retriable=True)

        if response.status_code != 200:
            raise ThreatIntelProviderError(
                self.name, f"unexpected status {response.status_code}: {response.text[:200]}"
            )

        try:
            payload = response.json()
            data = payload["data"]
            confidence_score = int(data["abuseConfidenceScore"])
            total_reports = data.get("totalReports", 0)
        except (KeyError, ValueError, TypeError) as exc:
            raise ThreatIntelProviderError(self.name, f"malformed response: {exc}") from exc

        severity = _severity_from_confidence(confidence_score)
        reputation = (
            f"{confidence_score}% abuse confidence ({total_reports} reports)"
            if total_reports
            else "no abuse reports on file"
        )

        return ThreatIntelResult(
            indicator=indicator,
            type=indicator_type,
            risk_score=confidence_score,
            severity=severity,
            reputation=reputation,
            source=self.name,
            raw=payload,
            confidence=0.85,
        )
