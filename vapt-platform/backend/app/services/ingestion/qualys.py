"""Qualys WAS / Qualys scan XML parser (lightweight).

Two document shapes:
  * `<WAS_SCAN_REPORT>` with `<VULNERABILITY>` children
  * `<SCAN>` with `<RESULTS><RESULT>` children

We normalise both to a list of NormalizedItem. Severity text is
mapped (Critical/High/Medium/Low/Informational).
"""

from __future__ import annotations

import re
from defusedxml import ElementTree as ET

from app.services.ingestion.nessus import NormalizedItem


_SEV_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "informational": "info",
    "info": "info",
    "minimal": "low",
    # Qualys WAS uses 1-5 numeric levels; map to canonical severities.
    "5": "critical",
    "4": "high",
    "3": "medium",
    "2": "low",
    "1": "info",
}

_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)


def _x_text(el) -> str | None:
    if el is None:
        return None
    return (el.text or "").strip() or None


def _coerce_port(s: str | None) -> tuple[int | None, str | None]:
    if not s:
        return None, None
    if "/" in s:
        p, proto = s.split("/", 1)
        try:
            return int(p), proto
        except ValueError:
            return None, proto or None
    try:
        return int(s), "tcp"
    except ValueError:
        return None, None


def _find_text(node, paths: list[str]) -> str | None:
    for p in paths:
        el = node.find(p)
        if el is not None and (el.text or "").strip():
            return el.text.strip()
    return None


def _build_was_item(vuln) -> NormalizedItem:
    host = _find_text(vuln, ["HOST/IP", "HOST", "host", "IP"]) or "unknown"
    port, proto = _coerce_port(_find_text(vuln, ["PORT", "port"]))
    sev = (_find_text(vuln, ["SEVERITY", "severity"]) or "info").lower()
    severity = _SEV_MAP.get(sev, "info")
    title = _find_text(vuln, ["TITLE", "title", "NAME", "name"]) or "Qualys WAS vulnerability"
    cve_raw = _find_text(vuln, ["CVE_ID", "CVE", "cve"]) or ""
    cve_id = None
    m = _CVE_RE.search(cve_raw)
    if m:
        cve_id = m.group(0).upper()
    diag = _find_text(vuln, ["DIAGNOSIS", "diagnosis", "DESCRIPTION", "description"]) or ""
    solution = _find_text(vuln, ["SOLUTION", "solution", "REMEDIATION", "remediation"]) or ""
    desc = diag
    if solution:
        desc = (desc + "\n\nRemediation:\n" + solution).strip() or title
    return NormalizedItem(
        asset_value=host,
        asset_type="ip" if _looks_like_ip(host) else "host",
        port=port,
        protocol=proto,
        title=title[:400],
        description=desc or title,
        severity=severity,
        cve_id=cve_id,
        plugin="qualys",
        plugin_id=_find_text(vuln, ["QID", "qid", "ID", "id"]),
    )


def _build_scan_result_item(result) -> NormalizedItem:
    host = result.get("host") or "unknown"
    port, proto = _coerce_port(result.get("port"))
    sev = (result.get("severity") or "info").lower()
    severity = _SEV_MAP.get(sev, "info")
    title = result.get("title") or "Qualys finding"
    return NormalizedItem(
        asset_value=host,
        asset_type="ip" if _looks_like_ip(host) else "host",
        port=port,
        protocol=proto,
        title=title[:400],
        description=result.get("description") or title,
        severity=severity,
        plugin="qualys",
        plugin_id=str(result.get("qid")) if result.get("qid") else None,
    )


def parse(xml_bytes: bytes) -> list[NormalizedItem]:
    root = ET.fromstring(xml_bytes)
    items: list[NormalizedItem] = []
    # WAS
    for vuln in root.iter("VULNERABILITY"):
        items.append(_build_was_item(vuln))
    # SCAN
    for result in root.iter("RESULT"):
        items.append(_build_scan_result_item({
            "host": _x_text(result.find("HOST")),
            "port": _x_text(result.find("PORT")),
            "severity": _x_text(result.find("SEVERITY")),
            "title": _x_text(result.find("TITLE")),
            "description": _x_text(result.find("DIAGNOSIS")),
            "qid": _x_text(result.find("QID")),
        }))
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
    if "qualys" in n:
        return True
    if b"<WAS_SCAN_REPORT" in head:
        return True
    if b"<SCAN" in head and b"<RESULT" in head:
        return True
    if n.endswith(".xml") and b"QID" in head:
        return True
    return False
