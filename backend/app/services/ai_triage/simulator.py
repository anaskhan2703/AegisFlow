"""
Simulator provider — deterministic, rule-based triage narrative generated
without calling any external API.

This is the fallback whenever GEMINI_API_KEY is blank or the Gemini call
fails for any reason. Same rationale as threat_intel/simulator.py: this is
a portfolio demo, not a production SOC, so a clearly-labeled templated
report beats a 500 error every time. Unlike the Gemini provider, there's
no need for hash-seeded randomness here — the alert's own severity,
correlation score, and indicator details already vary per alert, so
templating off those directly produces varied, alert-specific output
without needing to fake variety.
"""

from app.services.ai_triage.base import AlertTriageContext, TriageProvider, TriageResult

_ACTIONS_BY_TIER = {
    "critical": [
        "Isolate the affected host from the network immediately",
        "Escalate to incident response / on-call security lead",
        "Block all extracted indicators at the firewall/proxy",
        "Preserve forensic evidence (memory, disk image) before remediation",
    ],
    "high": [
        "Isolate or closely monitor the affected host",
        "Block the extracted indicators at the firewall/proxy",
        "Review authentication and process logs for the affected host/user",
    ],
    "medium": [
        "Review the alert context and affected host for related activity",
        "Add extracted indicators to a watchlist for continued monitoring",
    ],
    "low": [
        "Log for awareness; no immediate action required",
        "Re-evaluate if additional related alerts appear",
    ],
}


def _tier_for_score(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


class SimulatorProvider(TriageProvider):
    name = "simulated"

    async def triage(self, context: AlertTriageContext) -> TriageResult:
        tier = _tier_for_score(context.correlation_score)
        bad_indicators = [
            d
            for d in context.indicator_details
            if str(d.get("severity", "")).lower() in ("high", "critical")
        ]

        if bad_indicators:
            indicator_note = (
                f"{len(bad_indicators)} of {len(context.indicator_details)} extracted "
                f"indicator(s) resolved as high/critical severity."
            )
        elif context.indicator_details:
            indicator_note = (
                f"{len(context.indicator_details)} indicator(s) extracted; none resolved "
                f"above medium severity."
            )
        else:
            indicator_note = "No indicators were extracted from this alert's payload."

        summary = (
            f"[Simulated triage] A '{context.alert_type}' alert was raised for "
            f"{context.hostname or 'an unidentified host'}"
            f"{f' (user: {context.user})' if context.user else ''}, "
            f"reported at {context.severity} severity with a correlation score of "
            f"{context.correlation_score}/100 ({tier} tier). {indicator_note} This is a "
            f"rule-based placeholder report — no external AI model was called."
        )

        return TriageResult(
            summary=summary,
            mitre_technique=context.mitre_technique,
            recommended_actions=_ACTIONS_BY_TIER[tier],
            provider=self.name,
            raw={
                "engine": "aegisflow-triage-simulator",
                "note": "This result is simulated dummy data — no AI model was called.",
                "tier": tier,
                "correlation_score": context.correlation_score,
            },
            confidence=0.5,
        )
