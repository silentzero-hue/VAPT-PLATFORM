"""OWASP ZAP XML report parser.

Each `<alertitem>` becomes one item. ZAP risk codes:
  0 = Informational
  1 = Low
  2 = Medium
  3 = High
Confidence is intentionally NOT used to set severity.
"""

from __future__ import annotations

from defusedxml import ElementTree as ET

from app.services.ingestion.nessus import NormalizedItem


_RISK_MAP = {
    "0": "info",
    "1": "low",
    "2": "medium",
    "3": "high",
}


def _x_text(el) -> str | None:
    if el is None:
        return None
    return (el.text or "").strip() or None


def parse(xml_bytes: bytes) -> list[NormalizedItem]:
    root = ET.fromstring(xml_bytes)
    items: list[NormalizedItem] = []
    for alert in root.iter("alertitem"):
        risk_code = (_x_text(alert.find("riskcode")) or "0").strip()
        severity = _RISK_MAP.get(risk_code, "info")
        host = _x_text(alert.find("host")) or "unknown"
        port_raw = _x_text(alert.find("port"))
        try:
            port = int(port_raw) if port_raw else None
        except ValueError:
            port = None
        title = _x_text(alert.find("name")) or "ZAP alert"
        plugin_id = _x_text(alert.find("pluginid")) or ""
        desc_parts = []
        if (d := _x_text(alert.find("desc"))):
            desc_parts.append(d)
        if (s := _x_text(alert.find("solution"))):
            desc_parts.append("Remediation:\n" + s)
        if (refs := _x_text(alert.find("reference"))):
            desc_parts.append("References:\n" + refs)
        items.append(NormalizedItem(
            asset_value=host,
            asset_type="host",
            port=port,
            protocol="tcp" if port else None,
            title=title[:400],
            description="\n\n".join(desc_parts) or title,
            severity=severity,
            plugin="zap",
            plugin_id=plugin_id or None,
            cwe_id=f"CWE-{_x_text(alert.find('cweid')) or ''}" if _x_text(alert.find("cweid")) else None,
            evidence=_x_text(alert.find("evidence")) or _x_text(alert.find("uri")),
            extra={
                "method": _x_text(alert.find("method")),
                "uri": _x_text(alert.find("uri")),
                "confidence": _x_text(alert.find("confidence")),
                "risk_desc": _x_text(alert.find("riskdesc")),
            },
        ))
    return items


def detect(filename: str, head: bytes) -> bool:
    n = filename.lower()
    if "zap" in n and n.endswith(".xml"):
        return True
    if b"<OWASPZAPReport" in head or b"owasp_zap_report" in head.lower():
        return True
    if n.endswith(".xml") and b"alertitem" in head:
        return True
    return False
