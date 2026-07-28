"""Nmap XML parser."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from defusedxml import ElementTree as ET

from app.services.ingestion.nessus import NormalizedItem  # reuse shape


@dataclass
class _PortInfo:
    port: int
    protocol: str
    service: str = ""
    product: str = ""
    version: str = ""
    state: str = ""


def parse(xml_bytes: bytes) -> list[NormalizedItem]:
    root = ET.fromstring(xml_bytes)
    out: list[NormalizedItem] = []
    for host in root.findall("host"):
        address = host.find("address")
        hostnames = host.find("hostnames")
        if address is None:
            continue
        ip = address.get("addr", "")
        fqdn_el = hostnames.find("hostname") if hostnames is not None else None
        fqdn = fqdn_el.get("name") if fqdn_el is not None else None
        asset_value = fqdn or ip

        ports: list[_PortInfo] = []
        for port in host.findall("ports/port"):
            try:
                pnum = int(port.get("portid", "0"))
            except ValueError:
                continue
            proto = port.get("protocol", "tcp")
            state_el = port.find("state")
            state = state_el.get("state", "") if state_el is not None else ""
            svc_el = port.find("service")
            svc_attrs = {
                "name": svc_el.get("name", "") if svc_el is not None else "",
                "product": svc_el.get("product", "") if svc_el is not None else "",
                "version": svc_el.get("version", "") if svc_el is not None else "",
            }
            ports.append(_PortInfo(
                port=pnum, protocol=proto,
                service=svc_attrs["name"],
                product=svc_attrs["product"],
                version=svc_attrs["version"],
                state=state,
            ))

        # No script output → we generate one NormalizedItem per port that is open
        # (a "service exposure" finding), severity based on port category.
        for p in ports:
            if p.state not in ("open", "open|filtered"):
                continue
            sev = _port_severity(p.port, p.service)
            desc = (
                f"Open port {p.port}/{p.protocol} on {asset_value}\n"
                f"Service: {p.service or 'unknown'}\n"
                f"Product: {p.product or '-'}\n"
                f"Version: {p.version or '-'}"
            ).strip()
            out.append(NormalizedItem(
                asset_value=asset_value, asset_type="ip",
                port=p.port, protocol=p.protocol,
                title=f"Open port {p.port}/{p.protocol} ({p.service or 'unknown'})",
                description=desc, severity=sev,
                plugin="nmap", plugin_id=f"nmap-port-{p.port}-{p.protocol}",
                extra={"service": p.service, "product": p.product, "version": p.version},
            ))

        # Script output → vulnerabilities
        for port in host.findall("ports/port"):
            for script in port.findall("script"):
                sid = script.get("id", "")
                outp = script.get("output", "")
                if not outp:
                    continue
                sev = _script_severity(outp)
                out.append(NormalizedItem(
                    asset_value=asset_value, asset_type="ip",
                    port=int(port.get("portid", "0")) or None,
                    protocol=port.get("protocol"),
                    title=f"Nmap {sid} on {asset_value}",
                    description=outp, severity=sev,
                    plugin="nmap", plugin_id=sid,
                    evidence=outp[:8000],
                    extra={"nse_script": sid},
                ))
    return out


_RISKY_PORTS = {
    21: "high", 22: "medium", 23: "high", 25: "low", 53: "low",
    80: "low", 110: "medium", 111: "medium", 135: "medium", 139: "high",
    143: "medium", 161: "low", 389: "medium", 443: "info", 445: "high",
    465: "low", 514: "medium", 587: "low", 636: "low", 873: "medium",
    993: "low", 995: "low", 1433: "high", 1521: "high", 2049: "medium",
    2375: "critical", 2376: "high", 3000: "low", 3306: "high", 3389: "high",
    4505: "medium", 4506: "medium", 5000: "low", 5432: "high", 5601: "low",
    5900: "high", 5984: "medium", 6379: "high", 7001: "medium", 8000: "low",
    8008: "low", 8080: "low", 8081: "low", 8443: "low", 8500: "low",
    9000: "low", 9042: "medium", 9090: "low", 9092: "low", 9200: "high",
    9300: "high", 11211: "high", 15672: "medium", 27017: "high", 50070: "high",
}


def _port_severity(port: int, service: str) -> str:
    if port in _RISKY_PORTS:
        return _RISKY_PORTS[port]
    if service in {"telnet", "rsh", "rlogin", "vnc"}:
        return "high"
    if service in {"http", "https", "http-proxy", "http-alt"}:
        return "info"
    return "low"


def _script_severity(out: str) -> str:
    s = out.lower()
    if re.search(r"\bvuln|cve-\d{4}-\d+|exploit", s):
        return "high"
    if re.search(r"\bstate:\s*vuln|state:\s*open\s*$", s, re.M):
        return "medium"
    return "low"
