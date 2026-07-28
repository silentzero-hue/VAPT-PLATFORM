"""Nessus .nessus (XML v2) parser."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from defusedxml import ElementTree as ET


@dataclass
class NormalizedItem:
    """Common shape produced by every parser; the dedup engine
    consumes this regardless of source format."""
    asset_value: str
    asset_type: str = "host"
    port: int | None = None
    protocol: str | None = None
    title: str = ""
    description: str = ""
    severity: str = "medium"  # critical|high|medium|low|info
    cve_id: str | None = None
    cwe_id: str | None = None
    plugin: str | None = None
    plugin_id: str | None = None
    references: list[str] = field(default_factory=list)
    cvss_score: float | None = None
    evidence: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


_SEV_MAP = {
    "4": "critical",
    "3": "high",
    "2": "medium",
    "1": "low",
    "0": "info",
}


def _x_text(el) -> str | None:  # type: ignore[no-untyped-def]
    if el is None:
        return None
    return (el.text or "").strip() or None


def parse(xml_bytes: bytes) -> list[NormalizedItem]:
    root = ET.fromstring(xml_bytes)
    items: list[NormalizedItem] = []
    now = datetime.now(timezone.utc)

    for report in root.findall("Report"):
        for host in report.findall("ReportHost"):
            host_name = host.get("name", "")
            host_ip = None
            for prop in host.findall("HostProperties/tag"):
                if prop.get("name") == "host-ip":
                    host_ip = prop.text
            asset_value = host_ip or host_name

            for item in host.findall("ReportItem"):
                plugin_id = item.get("pluginID")
                plugin_name = item.get("pluginName", "")
                port = int(item.get("port", "0"))
                protocol = item.get("protocol")
                severity_raw = item.get("severity", "0")
                severity = _SEV_MAP.get(severity_raw, "info")

                cves: list[str] = []
                for cve in item.findall("cve"):
                    if cve.text:
                        cves.append(cve.text.strip())
                cwe_raw = _x_text(item.find("cwe"))
                cwe_id = f"CWE-{cwe_raw}" if cwe_raw and not cwe_raw.upper().startswith("CWE-") else cwe_raw

                description = ""
                for tag in ("description", "synopsis", "plugin_output"):
                    t = _x_text(item.find(tag))
                    if t:
                        description += f"[{tag}] {t}\n\n"

                refs: list[str] = []
                for ref in item.findall("see_also"):
                    if ref.text:
                        refs.append(ref.text.strip())
                for url in item.findall("url"):
                    if url.text:
                        refs.append(url.text.strip())

                evidence = _x_text(item.find("plugin_output"))
                cvss_raw = _x_text(item.find("cvss3_base_score")) or _x_text(item.find("cvss_base_score"))
                cvss_score = float(cvss_raw) if cvss_raw else None

                items.append(NormalizedItem(
                    asset_value=asset_value,
                    asset_type="ip" if host_ip and _looks_like_ip(asset_value) else "host",
                    port=port, protocol=protocol,
                    title=plugin_name[:400] or f"Nessus plugin {plugin_id}",
                    description=description.strip() or plugin_name,
                    severity=severity,
                    cvss_score=cvss_score,
                    cve_id=cves[0] if cves else None,
                    cwe_id=cwe_id,
                    plugin="nessus",
                    plugin_id=plugin_id,
                    references=refs,
                    evidence=evidence,
                    raw={"first_seen": now.isoformat()},
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
