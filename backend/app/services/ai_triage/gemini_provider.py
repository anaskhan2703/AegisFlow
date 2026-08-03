"""
Gemini provider (free tier).

Docs: https://ai.google.dev/api/generate-content
Calls the REST endpoint directly via httpx rather than pulling in the
google-generativeai SDK — httpx is already a dependency (see
threat_intel/virustotal.py), and a raw REST call keeps this provider's
failure modes explicit and easy to reason about, same as the other
providers in this codebase.

We ask Gemini to return JSON directly (responseMimeType) so we don't have
to regex a narrative response apart — this also keeps the shape stable
across model updates.
"""

import json

import httpx

from app.core.config import settings
from app.services.ai_triage.base import (
    AlertTriageContext,
    TriageProvider,
    TriageProviderError,
    TriageResult,
)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0)

_SYSTEM_INSTRUCTION = (
    "You are a SOC (Security Operations Center) triage assistant reviewing "
    "an already-correlated security alert. You are given the alert's "
    "metadata and the threat-intel verdicts for any indicators it contains. "
    "Respond ONLY with a JSON object — no markdown, no preamble — with "
    "exactly these keys:\n"
    '  "summary": 2-4 sentence plain-English narrative of what likely '
    "happened and why it matters, written for a SOC analyst.\n"
    '  "mitre_technique": your best-guess MITRE ATT&CK technique ID '
    '(e.g. "T1071"), or null if you cannot determine one confidently. '
    "Prefer the alert's existing mitre_technique field if it's already "
    "populated and looks correct.\n"
    '  "recommended_actions": a JSON array of 2-5 short, concrete next '
    "steps a SOC analyst should take (strings)."
)


def _build_prompt(context: AlertTriageContext) -> str:
    indicator_lines = (
        "\n".join(
            f"  - {d.get('indicator')} ({d.get('type')}): severity={d.get('severity')}, "
            f"reputation={d.get('reputation')}, risk_score={d.get('risk_score')}"
            for d in context.indicator_details
        )
        or "  (no indicators extracted)"
    )

    return (
        f"Alert type: {context.alert_type}\n"
        f"Hostname: {context.hostname or 'unknown'}\n"
        f"User: {context.user or 'unknown'}\n"
        f"Reported severity: {context.severity}\n"
        f"Current status: {context.status}\n"
        f"Existing MITRE technique (if any): {context.mitre_technique or 'none'}\n"
        f"Correlation score: {context.correlation_score}/100\n"
        f"Raw alert details: {json.dumps(context.details, default=str)}\n"
        f"Threat intel on extracted indicators:\n{indicator_lines}\n"
    )


class GeminiProvider(TriageProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL

    async def triage(self, context: AlertTriageContext) -> TriageResult:
        if not self.api_key:
            raise TriageProviderError(self.name, "no API key configured")

        url = f"{_BASE_URL}/{self.model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": _build_prompt(context)}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise TriageProviderError(self.name, "request timed out", retriable=True) from exc
        except httpx.RequestError as exc:
            raise TriageProviderError(self.name, f"request failed: {exc}", retriable=True) from exc

        if response.status_code == 429:
            raise TriageProviderError(self.name, "rate limited", retriable=True)

        if response.status_code != 200:
            raise TriageProviderError(
                self.name, f"unexpected status {response.status_code}: {response.text[:200]}"
            )

        try:
            payload = response.json()
            parts = payload["candidates"][0]["content"]["parts"]
            # Gemini 3.x "thinking" models can return a reasoning part ahead
            # of the actual answer part (flagged via "thought": true). Skip
            # those and use the first part that isn't marked as a thought,
            # rather than blindly trusting parts[0].
            answer_parts = [p for p in parts if not p.get("thought")]
            text = (answer_parts[0] if answer_parts else parts[0])["text"]
            parsed = json.loads(text)
            summary = parsed["summary"]
            mitre_technique = parsed.get("mitre_technique")
            recommended_actions = list(parsed.get("recommended_actions") or [])
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise TriageProviderError(self.name, f"malformed response: {exc}") from exc

        return TriageResult(
            summary=summary,
            mitre_technique=mitre_technique,
            recommended_actions=recommended_actions,
            provider=self.name,
            raw=payload,
            confidence=0.8,
        )