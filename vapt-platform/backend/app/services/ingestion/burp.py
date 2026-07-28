"""Burp Suite XML export parser.

Burp's `<issues>` root contains a flat list of `<issue>` elements.
Each one represents a finding for a (host, port, url) tuple.
"""

from __future__ import annotations

from defusedxml import ElementTree as ET

from app.services.ingestion.nessus import NormalizedItem


_SEV_MAP = {
    "high": "high",
    "medium": "medium",
    "low": "low",
    "information": "info",
    "informational": "info",
    "info": "info",
}


def _x_text(el) -> str | None:
    if el is None:
        return None
    return (el.text or "").strip() or None


def parse(xml_bytes: bytes) -> list[NormalizedItem]:
    root = ET.fromstring(xml_bytes)
    items: list[NormalizedItem] = []
    for issue in root.iter("issue"):
        severity = _SEV_MAP.get(
            (_x_text(issue.find("severity")) or "").lower(), "info"
        )
        host = _x_text(issue.find("host")) or _x_text(issue.find("hostip")) or "unknown"
        ip = _x_text(issue.find("hostip"))
        port_raw = _x_text(issue.find("port"))
        try:
            port = int(port_raw) if port_raw else None
        except ValueError:
            port = None
        title = _x_text(issue.find("name")) or "Burp issue"
        type_index = (
            issue.get("type")
            or _x_text(issue.find("type"))
            or "0"
        )
        background = _x_text(issue.find("issueBackground")) or ""
        remediation = _x_text(issue.find("remediationBackground")) or ""
        desc = background
        if remediation:
            desc = (desc + "\n\nRemediation:\n" + remediation).strip()
        location = _x_text(issue.find("location")) or ""
        items.append(NormalizedItem(
            asset_value=ip or host,
            asset_type="ip" if ip and _looks_like_ip(ip) else "host",
            port=port,
            protocol="tcp" if port else None,
            title=title[:400],
            description=desc or title,
            severity=severity,
            plugin="burp",
            plugin_id=f"burp:{type_index}",
            evidence=location,
            extra={"host": host, "path": location, "type_index": type_index},
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
    if "burp" in n and n.endswith(".xml"):
        return True
    if n.endswith(".xml") and b"<issues" in head and b"<issue" in head:
        return True
    return False
