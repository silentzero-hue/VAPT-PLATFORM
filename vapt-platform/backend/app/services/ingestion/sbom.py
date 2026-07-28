"""SBOM-aware ingestion: CycloneDX (JSON/XML) and SPDX parsers.

A SBOM is *not* a vulnerability scanner output, but it is a key
attack-surface map: knowing "this container has log4j 2.14.0" is
the input to vulnerability matching. The parser returns a list of
components which we upsert as assets (kind="repo" or "app") and
flag any whose version is known-vulnerable (we don't have a vuln
DB at parse time; that's a background job).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from defusedxml import ElementTree as ET


@dataclass
class Component:
    name: str
    version: str | None
    purl: str | None = None
    cpe: str | None = None
    ecosystem: str | None = None  # npm | pypi | maven | gem | nuget | go | generic
    licenses: list[str] = field(default_factory=list)
    supplier: str | None = None


def parse_cyclonedx(blob: bytes) -> list[Component]:
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        # try XML
        root = ET.fromstring(blob)
        out: list[Component] = []
        for c in root.iter():
            if c.tag.lower().endswith("component"):
                name = c.attrib.get("name") or c.findtext("name") or ""
                ver = c.attrib.get("version") or c.findtext("version")
                if name:
                    out.append(Component(name=name, version=ver))
        return out
    out: list[Component] = []
    for c in data.get("components", []) or []:
        out.append(Component(
            name=c.get("name", ""),
            version=c.get("version"),
            purl=c.get("purl"),
            cpe=c.get("cpe"),
            ecosystem=(c.get("purl") or "").split(":", 1)[0].lstrip("pkg:") if c.get("purl") else None,
            licenses=[l.get("license", {}).get("name", "") for l in (c.get("licenses") or []) if l.get("license")],
            supplier=(c.get("supplier") or {}).get("name"),
        ))
    return out


def parse_spdx(blob: bytes) -> list[Component]:
    """SPDX 2.x JSON. We deliberately support the JSON variant; tag-value
    is parseable too but adds complexity for marginal benefit."""
    data = json.loads(blob)
    out: list[Component] = []
    for p in data.get("packages", []) or []:
        ver = p.get("versionInfo")
        purl = None
        for ref in p.get("externalRefs", []) or []:
            if ref.get("referenceType") == "purl":
                purl = ref.get("referenceLocator")
                break
        out.append(Component(
            name=p.get("name", ""),
            version=ver,
            purl=purl,
            ecosystem=(purl or "").split(":", 1)[0].lstrip("pkg:") if purl else None,
            licenses=[lc.get("license", "") for lc in (p.get("licenseDeclared") or "").split(" OR ")],
        ))
    return out


def detect_format(filename: str, head: bytes) -> str:
    if filename.lower().endswith((".cdx.json", ".cyclonedx.json")):
        return "cyclonedx"
    if filename.lower().endswith((".spdx.json",)):
        return "spdx"
    try:
        data = json.loads(head)
    except Exception:
        return "unknown"
    if data.get("bomFormat") == "CycloneDX":
        return "cyclonedx"
    if data.get("spdxVersion"):
        return "spdx"
    return "unknown"
