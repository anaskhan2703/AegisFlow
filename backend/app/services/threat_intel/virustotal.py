"""
VirusTotal provider (free tier).

Docs: https://developers.virustotal.com/reference/overview
Free tier is rate-limited (roughly 4 req/min, 500/day) and can be slow, so
every call here has an explicit timeout — we'd rather fail fast and let the
caller fall back / surface an error than hang a user's request.
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

_BASE_URL = "https://www.virustotal.com/api/v3"
_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)

# VirusTotal uses different URL path segments per indicator type.
_ENDPOINT_BY_TYPE = {
    IndicatorType.IP: "ip_addresses",
    IndicatorType.DOMAIN: "domains",
    IndicatorType.HASH: "files",
    IndicatorType.URL: "urls",
}


def _severity_from_malicious_count(malicious: int, total: int) -> Severity:
    if total == 0:
        return Severity.NONE
    ratio = malicious / total
    if ratio >= 0.5:
        return Severity.CRITICAL
    if ratio >= 0.25:
        return Severity.HIGH
    if ratio >= 0.1:
        return Severity.MEDIUM
    if malicious > 0:
        return Severity.LOW
    return Severity.NONE


class VirusTotalProvider(ThreatIntelProvider):
    name = "virustotal"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.VIRUSTOTAL_API_KEY

    async def lookup(self, indicator: str, indicator_type: IndicatorType) -> ThreatIntelResult:
        if not self.api_key:
            raise ThreatIntelProviderError(self.name, "no API key configured")

        segment = _ENDPOINT_BY_TYPE.get(indicator_type)
        if segment is None:
            raise ThreatIntelProviderError(self.name, f"unsupported indicator type: {indicator_type}")

        # VirusTotal expects file hashes and URLs identified differently, but
        # for URLs it wants a base64-urlsafe-encoded, unpadded identifier.
        identifier = indicator
        if indicator_type == IndicatorType.URL:
            import base64
            identifier = base64.urlsafe_b64encode(indicator.encode()).decode().rstrip("=")

        url = f"{_BASE_URL}/{segment}/{identifier}"
        headers = {"x-apikey": self.api_key}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise ThreatIntelProviderError(self.name, "request timed out", retriable=True) from exc
        except httpx.RequestError as exc:
            raise ThreatIntelProviderError(self.name, f"request failed: {exc}", retriable=True) from exc

        if response.status_code == 404:
            # Unknown to VirusTotal isn't an error — it's a "clean/no data" verdict.
            return ThreatIntelResult(
                indicator=indicator,
                type=indicator_type,
                risk_score=0,
                severity=Severity.NONE,
                reputation="unknown (no VirusTotal data)",
                source=self.name,
                raw={"status_code": 404},
                confidence=0.2,
            )

        if response.status_code == 429:
            raise ThreatIntelProviderError(self.name, "rate limited", retriable=True)

        if response.status_code != 200:
            raise ThreatIntelProviderError(
                self.name, f"unexpected status {response.status_code}: {response.text[:200]}"
            )

        try:
            payload = response.json()
            attributes = payload["data"]["attributes"]
            stats = attributes["last_analysis_stats"]
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            total = sum(stats.values()) or 1
        except (KeyError, ValueError, TypeError) as exc:
            raise ThreatIntelProviderError(self.name, f"malformed response: {exc}") from exc

        weighted = malicious + (suspicious * 0.5)
        risk_score = min(100, round((weighted / total) * 100))
        severity = _severity_from_malicious_count(malicious, total)
        reputation = (
            f"{malicious}/{total} engines flagged malicious"
            if malicious
            else "no engines flagged this indicator"
        )

        return ThreatIntelResult(
            indicator=indicator,
            type=indicator_type,
            risk_score=risk_score,
            severity=severity,
            reputation=reputation,
            source=self.name,
            raw=payload,
            confidence=0.9,
        )
