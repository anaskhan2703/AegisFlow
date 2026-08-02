"""
Factory / selector for threat intel providers.

Selection logic (in order, per indicator type):
  1. If a real provider is configured (API key present) AND supports this
     indicator type, use it as the primary. IPs prefer AbuseIPDB first (it's
     abuse-report focused and free-tier friendly), then fall back to
     VirusTotal if AbuseIPDB has no key or fails. Everything else (domain,
     hash, url) goes straight to VirusTotal since AbuseIPDB only does IPs.
  2. If no real provider is configured/available, or the real provider call
     fails, fall back to the simulator so the endpoint always returns
     *something* usable — this is a portfolio demo, not a production SOC,
     so "clearly-labeled fake data" beats "500 error" every time.

This module is the only place that should ever import a concrete provider
class directly — everywhere else (the endpoint, tests) should depend on the
ThreatIntelProvider interface and call get_providers_for(indicator_type).
"""

import logging

from app.core.config import settings
from app.services.threat_intel.abuseipdb import AbuseIPDBProvider
from app.services.threat_intel.base import (
    IndicatorType,
    ThreatIntelProvider,
    ThreatIntelProviderError,
    ThreatIntelResult,
    Severity,
)
from app.services.threat_intel.simulator import SimulatorProvider
from app.services.threat_intel.virustotal import VirusTotalProvider

logger = logging.getLogger(__name__)

_simulator = SimulatorProvider()


def _ordered_real_providers(indicator_type: IndicatorType) -> list[ThreatIntelProvider]:
    """Real (non-simulated) providers to try, in priority order, for a given
    indicator type. Only includes providers that both support this type AND
    have an API key configured."""
    candidates: list[ThreatIntelProvider] = []

    if indicator_type == IndicatorType.IP and settings.ABUSEIPDB_API_KEY:
        candidates.append(AbuseIPDBProvider())

    if settings.VIRUSTOTAL_API_KEY:
        vt = VirusTotalProvider()
        if vt.supports(indicator_type):
            candidates.append(vt)

    return candidates


async def lookup_indicator(indicator: str, indicator_type: IndicatorType) -> ThreatIntelResult:
    """
    Single entry point used by the API layer. Tries real providers first (if
    configured), falls back to the simulator on failure or absence of keys.
    Never raises — always returns a usable ThreatIntelResult.
    """
    for provider in _ordered_real_providers(indicator_type):
        try:
            return await provider.lookup(indicator, indicator_type)
        except ThreatIntelProviderError as exc:
            logger.warning("Threat intel provider %s failed, trying next: %s", provider.name, exc)
            continue

    # No real provider configured, or all of them failed — simulate.
    return await _simulator.lookup(indicator, indicator_type)


__all__ = [
    "lookup_indicator",
    "IndicatorType",
    "Severity",
    "ThreatIntelResult",
    "ThreatIntelProvider",
    "ThreatIntelProviderError",
]
