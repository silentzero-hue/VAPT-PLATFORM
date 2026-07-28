"""OpenVAS / GVM XML report parser.

The typical report root is `<get_reports_response>` containing one or
more `<report>` elements. Each `<result>` is a finding. `host`,
`port`, `threat`, and the inner `<name>` element are the fields we
need; the `<nvt>` block carries plugin/CVE metadata.
"""

from __future__ import annotations

import re
from defusedxml import ElementTree as ET

from app.services.ingestion.nessus import NormalizedItem


_THREAT_MAP = {
    "high": "high",
    "medium": "medium",
    "low": "low",
    "informational": "info",
    "info": "info",
    "log": "info",
    "debug": "info",
    "critical": "critical",
}

_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)
_BID_RE = re.compile(r"\bBID-?\s*(\d+)", re.IGNORECASE)


def _x_text(el) -> str | None:
    if el is None:
        return None
    return (el.text or "").strip() or None


def _port_from_string(s: str | None) -> tuple[int | None, str | None]:
    if not s:
        return None, None
    s = s.strip()
    # common shapes: "443/tcp", "general/tcp", "80"
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


def parse(xml_bytes: bytes) -> list[NormalizedItem]:
    root = ET.fromstring(xml_bytes)
    items: list[NormalizedItem] = []
    for result in root.iter("result"):
        host = _x_text(result.find("host")) or "unknown"
        # host text often includes the IP; strip leading whitespace
        host = host.strip() or "unknown"
        port_str = _x_text(result.find("port"))
        port, proto = _port_from_string(port_str)
        threat_raw = (_x_text(result.find("threat")) or "").lower()
        severity = _THREAT_MAP.get(threat_raw, "info")

        # OpenVAS names: the inner <name> is the human title; the
        # outer <name> of the NVT is the plugin name.
        nvt = result.find("nvt")
        plugin_name = _x_text(nvt.find("name")) if nvt is not None else None
        title = plugin_name or _x_text(result.find("name")) or "OpenVAS result"
        plugin_oid = _x_text(nvt.find("oid")) if nvt is not None else None

        desc_parts = []
        if (d := _x_text(result.find("description"))):
            desc_parts.append(d)
        cve_id = None
        if nvt is not None:
            for cve_node in nvt.findall("cve"):
                if cve_node.text and cve_id is None:
                    m = _CVE_RE.search(cve_node.text)
                    if m:
                        cve_id = m.group(0).upper()
            for tag in nvt.findall("tag"):
                if not tag.text:
                    continue
                if "cve:" in tag.text.lower() and cve_id is None:
                    m = _CVE_RE.search(tag.text)
                    if m:
                        cve_id = m.group(0).upper()
                if "bid:" in tag.text.lower():
                    m = _BID_RE.search(tag.text)
                    if m:
                        desc_parts.append("BID-" + m.group(1))
        refs: list[str] = []
        if nvt is not None:
            for ref in nvt.findall("refs/ref"):
                if ref.get("id"):
                    refs.append(str(ref.get("id")))
        items.append(NormalizedItem(
            asset_value=host,
            asset_type="ip" if _looks_like_ip(host) else "host",
            port=port,
            protocol=proto,
            title=title[:400],
            description="\n\n".join(desc_parts) or title,
            severity=severity,
            cve_id=cve_id,
            plugin="openvas",
            plugin_id=plugin_oid or None,
            references=refs,
            evidence=_x_text(result.find("host_detail")),
            extra={"threat": threat_raw, "port_raw": port_str},
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
    if "openvas" in n or "gvm" in n:
        return True
    if b"<get_reports_response" in head or b"<get_reports" in head:
        return True
    if n.endswith(".xml") and b"<report" in head and b"<result" in head and b"<nvt" in head:
        return True
    return False
