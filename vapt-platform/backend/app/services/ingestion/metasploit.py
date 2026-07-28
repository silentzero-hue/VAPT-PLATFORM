"""Metasploit `db_export -f xml` parser.

The MetasploitV5 export contains a `<vulns>` collection of `<vuln>`
entries; auxiliary scan results show up as `<note>` elements with a
`vuln` attribute. We treat each as a finding.
"""

from __future__ import annotations

import re
from defusedxml import ElementTree as ET

from app.services.ingestion.nessus import NormalizedItem


_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)
_SEV_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "info",
    "informational": "info",
}


def _x_text(el) -> str | None:
    if el is None:
        return None
    return (el.text or "").strip() or None


def _severity_for(vuln) -> str:
    """Try to read a severity out of the vuln's nested info block."""
    info = vuln.find("info")
    if info is None:
        return "info"
    sev = (_x_text(info.find("severity")) or "").lower()
    if sev in _SEV_MAP:
        return _SEV_MAP[sev]
    cvss = _x_text(info.find("cvss"))
    if cvss:
        try:
            s = float(cvss)
        except ValueError:
            return "medium"
        if s >= 9.0:
            return "critical"
        if s >= 7.0:
            return "high"
        if s >= 4.0:
            return "medium"
        if s > 0.0:
            return "low"
    return "medium"


def parse(xml_bytes: bytes) -> list[NormalizedItem]:
    root = ET.fromstring(xml_bytes)
    items: list[NormalizedItem] = []
    # <vulns>/<vuln>
    for vuln in root.iter("vuln"):
        host = _x_text(vuln.find("host")) or "unknown"
        try:
            port = int(_x_text(vuln.find("port")) or 0) or None
        except (TypeError, ValueError):
            port = None
        try:
            svc = _x_text(vuln.find("service")) or ""
        except Exception:
            svc = ""
        name = _x_text(vuln.find("name")) or "Metasploit finding"
        info = vuln.find("info")
        desc_parts = []
        cve_id = None
        if info is not None:
            if (d := _x_text(info.find("description"))):
                desc_parts.append(d)
            if (cv := _x_text(info.find("cvss"))):
                desc_parts.append("CVSS: " + cv)
            refs_node = info.find("refs")
            if refs_node is not None:
                for ref in refs_node.findall("ref"):
                    if ref.text:
                        m = _CVE_RE.search(ref.text)
                        if m and not cve_id:
                            cve_id = m.group(0).upper()
                        desc_parts.append("Ref: " + ref.text)
        items.append(NormalizedItem(
            asset_value=host,
            asset_type="ip" if _looks_like_ip(host) else "host",
            port=port,
            protocol=svc or ("tcp" if port else None),
            title=name[:400],
            description="\n\n".join(desc_parts) or name,
            severity=_severity_for(vuln),
            cve_id=cve_id,
            plugin="metasploit",
            plugin_id=_x_text(vuln.find("module")) or None,
            evidence=_x_text(vuln.find("info/refs/ref")),
            extra={"service": svc, "exploited": _x_text(vuln.find("exploited"))},
        ))
    # <notes>/<note type="vuln">
    for note in root.iter("note"):
        if (note.get("type") or "") != "vuln":
            continue
        host = _x_text(note.find("host")) or "unknown"
        try:
            port = int(_x_text(note.find("port")) or 0) or None
        except (TypeError, ValueError):
            port = None
        items.append(NormalizedItem(
            asset_value=host,
            asset_type="ip" if _looks_like_ip(host) else "host",
            port=port,
            protocol="tcp" if port else None,
            title="Metasploit note",
            description=_x_text(note.find("data")) or "",
            severity="info",
            plugin="metasploit",
            plugin_id=_x_text(note.find("module")),
            extra={"note": True},
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
    if "metasploit" in n or "msf_" in n:
        return True
    if b"<MetasploitV5" in head:
        return True
    if n.endswith(".xml") and b"<vulns" in head and b"<vuln" in head:
        return True
    return False
