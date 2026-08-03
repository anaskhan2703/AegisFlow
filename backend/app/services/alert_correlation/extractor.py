"""Regex-based indicator extraction from raw alert payloads.

Given an arbitrary JSON-ish alert payload (dict, list, or scalar), this
walks the whole structure, stringifies it, and pulls out anything that
looks like an IP, domain, file hash, or URL. It also "refangs" common
defanged notations (hxxp, [.], (dot), etc.) since SOC tooling and threat
intel feeds routinely write indicators defanged to avoid them being
clickable/live.

This is intentionally simple pattern-matching, not a full parser -- good
enough for a portfolio-quality SIEM alert simulator, not meant to be a
production-grade IOC extraction engine.
"""
import re
import json
from typing import Any

IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b")

# Hex strings of common hash lengths: md5=32, sha1=40, sha256=64
HASH_RE = re.compile(r"\b[a-fA-F0-9]{64}\b|\b[a-fA-F0-9]{40}\b|\b[a-fA-F0-9]{32}\b")

URL_RE = re.compile(r"\bhttps?://[^\s\"'<>\)\]]+", re.IGNORECASE)

# Reasonably conservative domain matcher: label.label.tld, 2+ letter TLD,
# not preceded by an "@" (to avoid grabbing email local-parts) and not a
# pure IP (those are caught by IPV4_RE separately).
DOMAIN_RE = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,24}\b"
)

COMMON_TLD_NOISE = {"exe", "dll", "json", "log", "txt", "py", "js", "png", "jpg"}


def _refang(text: str) -> str:
    """Undo common defanging conventions so regexes can match normally."""
    replacements = [
        (r"hxxps?://", lambda m: m.group(0).replace("hxxp", "http")),
    ]
    text = re.sub(r"hxxp", "http", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\.\]|\(\.\)|\[dot\]|\(dot\)", ".", text, flags=re.IGNORECASE)
    text = re.sub(r"\[:\]", ":", text)
    text = re.sub(r"\[at\]|\(at\)", "@", text, flags=re.IGNORECASE)
    return text


def _flatten_to_text(payload: Any) -> str:
    """Turn an arbitrary JSON-like structure into one blob of text to
    scan. Using json.dumps keeps nested values (lists, nested dicts)
    from being skipped by a shallow str() walk.
    """
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, default=str)
    except TypeError:
        return str(payload)


def classify(value: str) -> str:
    if IPV4_RE.fullmatch(value):
        return "ip"
    if HASH_RE.fullmatch(value):
        return "hash"
    if value.lower().startswith(("http://", "https://")):
        return "url"
    return "domain"


def extract_indicators(payload: Any) -> list[dict]:
    """Return a de-duplicated list of {"indicator": str, "type": str}
    extracted from the payload, preserving first-seen order.
    """
    text = _refang(_flatten_to_text(payload))

    found: dict[str, str] = {}

    for m in URL_RE.finditer(text):
        found.setdefault(m.group(0).rstrip(".,;\"'"), "url")

    for m in IPV4_RE.finditer(text):
        found.setdefault(m.group(0), "ip")

    for m in HASH_RE.finditer(text):
        found.setdefault(m.group(0).lower(), "hash")

    for m in DOMAIN_RE.finditer(text):
        candidate = m.group(0).rstrip(".,;")
        if candidate in found:
            continue
        if IPV4_RE.fullmatch(candidate):
            continue
        tld = candidate.rsplit(".", 1)[-1].lower()
        if tld in COMMON_TLD_NOISE:
            continue
        # Skip domains that are actually the tail end of a URL we already caught
        if any(candidate in ind for ind, typ in found.items() if typ == "url"):
            continue
        found[candidate] = "domain"

    return [{"indicator": ind, "type": typ} for ind, typ in found.items()]
