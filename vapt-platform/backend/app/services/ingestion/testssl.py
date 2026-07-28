"""testssl.sh JSON output parser.

testssl.sh writes a flat `{"findings": [...]}` array of objects
with `id`, `severity`, `finding`, `ip`, `port`, and `cve`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.ingestion.nessus import NormalizedItem


_SEV_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "info",
    "informational": "info",
    "warn": "medium",
    "warning": "medium",
    "error": "info",
    "debug": "info",
    "fatal": "critical",
}

_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)


def _walk_findings(data: Any) -> list[dict]:
    if isinstance(data, dict) and isinstance(data.get("findings"), list):
        return [d for d in data["findings"] if isinstance(d, dict)]
    return []


def parse(blob: bytes) -> list[NormalizedItem]:
    data = json.loads(blob)
    items: list[NormalizedItem] = []
    for f in _walk_findings(data):
        sev_raw = (f.get("severity") or f.get("Severity") or "info").lower()
        severity = _SEV_MAP.get(sev_raw, "info")
        ip = f.get("ip") or "unknown"
        port_raw = f.get("port")
        if port_raw is None:
            port = 443
        else:
            try:
                port = int(port_raw)
            except (TypeError, ValueError):
                port = 443
        finding_text = f.get("finding") or f.get("id") or "testssl finding"
        cve = None
        m = _CVE_RE.search(str(finding_text))
        if m:
            cve = m.group(0).upper()
        elif (raw := f.get("cve")):
            cve = str(raw).upper() if _CVE_RE.search(str(raw)) else None
        items.append(NormalizedItem(
            asset_value=ip,
            asset_type="ip" if _looks_like_ip(ip) else "host",
            port=port,
            protocol="tcp",
            title=str(f.get("id") or "testssl finding")[:400],
            description=str(finding_text)[:8000],
            severity=severity,
            cve_id=cve,
            plugin="testssl",
            plugin_id=str(f.get("id")) if f.get("id") else None,
            extra={
                "fqdn": f.get("targetHost") or f.get("hostname"),
                "protocol": f.get("protocol"),
                "cipher": f.get("cipher"),
            },
        ))
    return items


def _looks_like_ip(s: str) -> bool:
    parts = s.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def detect(filename: str, head: bytes) -> bool:
    n = filename.lower()
    if "testssl" in n:
        return True
    if not n.endswith(".json"):
        return False
    try:
        data = json.loads(head if head else b"")
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    findings = data.get("findings")
    if not isinstance(findings, list) or not findings:
        return False
    first = findings[0]
    if not isinstance(first, dict):
        return False
    if "id" in first and "finding" in first and ("ip" in first or "port" in first):
        return True
    return False
