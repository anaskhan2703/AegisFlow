"""
Factory / selector for AI triage providers.

Selection logic:
  1. If GEMINI_API_KEY is configured, try Gemini as the primary.
  2. If no key is configured, or the Gemini call fails for any reason, fall
     back to the simulator so the endpoint always returns *something*
     usable — same "clearly-labeled fake data beats a 500 error" rationale
     as app/services/threat_intel/__init__.py.

This module is the only place that should ever import a concrete provider
class directly — everywhere else (the endpoint, tests) should depend on the
TriageProvider interface and call generate_triage_report(context).
"""

import logging

from app.core.config import settings
from app.services.ai_triage.base import (
    AlertTriageContext,
    TriageProvider,
    TriageProviderError,
    TriageResult,
)
from app.services.ai_triage.gemini_provider import GeminiProvider
from app.services.ai_triage.simulator import SimulatorProvider

logger = logging.getLogger(__name__)

_simulator = SimulatorProvider()


async def generate_triage_report(context: AlertTriageContext) -> TriageResult:
    """
    Single entry point used by the API layer. Tries Gemini first (if
    configured), falls back to the simulator on missing key or failure.
    Never raises — always returns a usable TriageResult.
    """
    if settings.GEMINI_API_KEY:
        try:
            return await GeminiProvider().triage(context)
        except TriageProviderError as exc:
            logger.warning("AI triage provider %s failed, falling back to simulator: %s", exc.provider, exc)

    return await _simulator.triage(context)


__all__ = [
    "generate_triage_report",
    "AlertTriageContext",
    "TriageResult",
    "TriageProvider",
    "TriageProviderError",
]
