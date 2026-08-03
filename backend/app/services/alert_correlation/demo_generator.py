"""Simulated SOC alert generator.

Produces realistic-looking alert payloads matching the real Alert
ingest shape (alert_type / hostname / user / details / severity /
mitre_technique) from a handful of templates. Each template mixes in a
known-bad indicator, a known-good indicator, or a random one (weighted
toward "bad" so demo alerts reliably show interesting correlation
scores), planted inside `details` where the correlation engine's
indicator extraction will find them.

Self-contained: this module defines its own small set of known-bad/
known-good indicators rather than depending on anything inside
threat_intel/simulator.py, since that module's internals are Phase 3's
concern, not this generator's.
"""
import random
import uuid
from datetime import datetime, timezone

KNOWN_BAD_IPS = ["185.220.101.45", "45.155.205.233", "194.165.16.63"]
KNOWN_BAD_DOMAINS = ["evil-c2-domain.net", "malware-drop.biz"]
KNOWN_GOOD_IPS = ["8.8.8.8", "1.1.1.1"]
KNOWN_GOOD_DOMAINS = ["google.com", "microsoft.com"]
KNOWN_BAD_HASHES = ["44d88612fea8a8f36de82e1278abb02f"]


def _random_ip() -> str:
    return ".".join(str(random.randint(1, 254)) for _ in range(4))


def _random_username() -> str:
    return random.choice(["jsmith", "aramirez", "kpatel", "svc_backup", "admin", "mchen"])


def _random_hostname() -> str:
    return f"WKSTN-{random.randint(1000, 9999)}"


def _pick_indicator(bad_pool: list[str], good_pool: list[str], bad_weight: float = 0.5) -> str:
    if random.random() < bad_weight and bad_pool:
        return random.choice(bad_pool)
    if good_pool and random.random() < 0.5:
        return random.choice(good_pool)
    return _random_ip()


def _template_brute_force() -> dict:
    src_ip = _pick_indicator(KNOWN_BAD_IPS, KNOWN_GOOD_IPS, bad_weight=0.6)
    user = _random_username()
    attempts = random.randint(8, 60)
    return {
        "alert_type": "brute_force",
        "hostname": _random_hostname(),
        "user": user,
        "severity": "medium",
        "mitre_technique": "T1110",
        "details": {
            "src_ip": src_ip,
            "target_user": user,
            "failed_attempts": attempts,
            "note": f"{attempts} failed authentication attempts from {src_ip} within 5 minutes, "
            f"followed by a successful login.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


def _template_c2_beacon() -> dict:
    domain = _pick_indicator(KNOWN_BAD_DOMAINS, KNOWN_GOOD_DOMAINS, bad_weight=0.7)
    host = _random_hostname()
    defanged_domain = domain.replace(".", "[.]")
    return {
        "alert_type": "c2_beacon",
        "hostname": host,
        "user": None,
        "severity": "high",
        "mitre_technique": "T1071",
        "details": {
            "dest_domain": domain,
            "beacon_interval_seconds": random.choice([30, 60, 300]),
            "connection_count": random.randint(20, 200),
            "note": f"Endpoint {host} making regular outbound connections to hxxps://{defanged_domain}/checkin, "
            f"consistent with C2 beacon behavior.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


def _template_suspicious_outbound() -> dict:
    dest_ip = _pick_indicator(KNOWN_BAD_IPS, KNOWN_GOOD_IPS, bad_weight=0.5)
    host = _random_hostname()
    port = random.choice([4444, 8080, 443, 6667, 9001])
    return {
        "alert_type": "suspicious_outbound",
        "hostname": host,
        "user": None,
        "severity": "medium",
        "mitre_technique": "T1571",
        "details": {
            "dest_ip": dest_ip,
            "dest_port": port,
            "note": f"Host {host} initiated an outbound connection to {dest_ip}:{port}, a destination not "
            f"previously seen from this segment.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


def _template_malware_download() -> dict:
    file_hash = random.choice(KNOWN_BAD_HASHES + [uuid.uuid4().hex + uuid.uuid4().hex[:8]])
    url_domain = _pick_indicator(KNOWN_BAD_DOMAINS, KNOWN_GOOD_DOMAINS, bad_weight=0.6)
    host = _random_hostname()
    defanged_domain = url_domain.replace(".", "[.]")
    return {
        "alert_type": "malware_download",
        "hostname": host,
        "user": None,
        "severity": "high",
        "mitre_technique": "T1105",
        "details": {
            "file_hash": file_hash,
            "source_url": f"http://{url_domain}/payload.exe",
            "note": f"Host {host} downloaded a file (hash {file_hash}) from hxxp://{defanged_domain}/payload.exe.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


def _template_port_scan() -> dict:
    src_ip = _pick_indicator(KNOWN_BAD_IPS, KNOWN_GOOD_IPS, bad_weight=0.4)
    target_subnet = f"10.0.{random.randint(0, 255)}.0/24"
    ports_scanned = random.randint(15, 200)
    return {
        "alert_type": "port_scan",
        "hostname": None,
        "user": None,
        "severity": "low",
        "mitre_technique": "T1046",
        "details": {
            "src_ip": src_ip,
            "target_subnet": target_subnet,
            "ports_scanned": ports_scanned,
            "note": f"Source {src_ip} scanned {ports_scanned} ports across {target_subnet} in under 60 seconds.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


TEMPLATES = {
    "brute_force": _template_brute_force,
    "c2_beacon": _template_c2_beacon,
    "suspicious_outbound": _template_suspicious_outbound,
    "malware_download": _template_malware_download,
    "port_scan": _template_port_scan,
}


def generate_demo_alerts(count: int = 5, template: str | None = None) -> list[dict]:
    """Generate `count` raw alert payloads matching the real Alert
    ingest shape. If `template` is given, all generated alerts use that
    template; otherwise templates are chosen at random for variety.
    """
    if template is not None and template not in TEMPLATES:
        raise ValueError(f"Unknown template '{template}'. Valid options: {list(TEMPLATES)}")

    generators = [TEMPLATES[template]] if template else list(TEMPLATES.values())
    return [random.choice(generators)() for _ in range(count)]
