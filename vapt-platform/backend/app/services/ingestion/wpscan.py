"""WPScan JSON output parser.

WPScan output has two key arrays: `findings` (vulnerabilities, weak
credentials, debug-log exposures, etc.) and `interesting_findings`
(fingerprinting results, no severity). We emit one item per entry
in `findings`. `interesting_findings` are emitted with severity=info.
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
    "unknown": "info",
}

_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)


def _walk(data: Any, key: str) -> list[tuple[str, dict]]:
    if isinstance(data, dict) and isinstance(data.get(key), dict):
        return [(k, v) for k, v in data[key].items() if isinstance(v, dict)]
    if isinstance(data, dict) and isinstance(data.get(key), list):
        return [(str(i), v) for i, v in enumerate(data[key]) if isinstance(v, dict)]
    return []


def _evidence_urls(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        if isinstance(v, dict) and v.get("url"):
            out.append(str(v["url"]))
    return out


def _vuln_to_item(target: str, k: str, v: dict) -> NormalizedItem:
    sev_raw = (v.get("severity") or v.get("risk") or "info").lower()
    severity = _SEV_MAP.get(sev_raw, "info")
    if v.get("confirmed") is True and severity == "info":
        severity = "medium"
    cve_id = None
    cve_ids = []
    for ident in v.get("identifiers", []) or []:
        if isinstance(ident, str) and _CVE_RE.match(ident):
            up = ident.upper()
            cve_ids.append(up)
            if cve_id is None:
                cve_id = up
    refs: list[str] = []
    for ref in v.get("references", []) or []:
        if isinstance(ref, dict) and ref.get("url"):
            refs.append(str(ref["url"]))
    return NormalizedItem(
        asset_value=target,
        asset_type="host",
        title=str(v.get("title") or v.get("type") or "WPScan finding")[:400],
        description=str(v.get("description") or v.get("title") or "")[:8000],
        severity=severity,
        cve_id=cve_id,
        plugin="wpscan",
        plugin_id=str(k),
        references=refs,
        evidence="\n".join(_evidence_urls(v.get("evidence"))),
        extra={
            "type": v.get("type"),
            "fixed_in": v.get("fixed_in"),
            "solution": v.get("solution"),
            "confirmed": v.get("confirmed"),
            "cve_ids": cve_ids,
        },
    )


def _interesting_to_item(target: str, k: str, v: dict) -> NormalizedItem:
    return NormalizedItem(
        asset_value=target,
        asset_type="host",
        title=str(v.get("title") or k)[:400],
        description=str(v.get("description") or v.get("to_s") or "")[:8000],
        severity="info",
        plugin="wpscan",
        plugin_id=f"interesting:{k}",
        extra={"type": v.get("type"), "interesting": True},
    )


def parse(blob: bytes) -> list[NormalizedItem]:
    data = json.loads(blob)
    target = "unknown"
    if isinstance(data, dict):
        target = data.get("target_url") or data.get("target") or "unknown"
    items: list[NormalizedItem] = []
    # findings: dict (keyed by slug) or list
    for k, v in _walk(data, "findings"):
        items.append(_vuln_to_item(target, k, v))
    for k, v in _walk(data, "interesting_findings"):
        items.append(_interesting_to_item(target, k, v))
    # also: version detection
    version = (data.get("version", {}) or {}) if isinstance(data, dict) else {}
    if version.get("number"):
        items.append(NormalizedItem(
            asset_value=target,
            asset_type="host",
            title=f"WordPress {version.get('number')} detected",
            description=f"WordPress version: {version.get('number')}\n"
                        f"Release status: {version.get('status') or 'unknown'}",
            severity="info",
            plugin="wpscan",
            plugin_id="version-detect",
        ))
    return items


def detect(filename: str, head: bytes) -> bool:
    n = filename.lower()
    if "wpscan" in n or "wp_scan" in n:
        return True
    if not n.endswith(".json"):
        return False
    try:
        data = json.loads(head if head else b"")
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    if "scan_aborted" in data or "target_url" in data:
        if "findings" in data or "interesting_findings" in data:
            return True
    return False
