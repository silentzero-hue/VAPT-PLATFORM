"""Trivy JSON report parser.

Trivy's JSON has a top-level `Results` array. Each result groups by
target (image, fs, iac). Inside, `Vulnerabilities` and
`Misconfigurations` arrays are the findings we care about.
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


def _pkg_kind(target: str) -> str:
    if target.startswith("container:"):
        return "container"
    if target.startswith("fs:"):
        return "fs"
    if "k8s" in target or "kubernetes" in target:
        return "k8s"
    return "package"


def _vuln_to_item(target: str, v: dict) -> NormalizedItem:
    severity = _SEV_MAP.get((v.get("Severity") or "unknown").lower(), "info")
    pkg = v.get("PkgName") or ""
    installed = v.get("InstalledVersion") or ""
    title = v.get("Title") or v.get("VulnerabilityID") or "Trivy vulnerability"
    cve = v.get("VulnerabilityID")
    if cve and not _CVE_RE.match(cve):
        cve = None
    refs: list[str] = []
    for ref in v.get("References", []) or []:
        if isinstance(ref, str):
            refs.append(ref)
    return NormalizedItem(
        asset_value=target,
        asset_type=_pkg_kind(target),
        title=title[:400],
        description=(
            f"Package: {pkg}\n"
            f"Installed version: {installed or '-'}\n"
            f"Fixed version: {v.get('FixedVersion') or '-'}\n\n"
            f"{v.get('Description') or ''}"
        ).strip(),
        severity=severity,
        cve_id=cve,
        cwe_id=v.get("CweIDs", [None])[0] if v.get("CweIDs") else None,
        plugin="trivy",
        plugin_id=v.get("VulnerabilityID") or None,
        references=refs,
        extra={
            "package": pkg,
            "installed_version": installed,
            "fixed_version": v.get("FixedVersion"),
            "target": target,
            "pkg_type": v.get("PkgType"),
            "data_source": v.get("DataSource"),
        },
    )


def _misconfig_to_item(target: str, m: dict) -> NormalizedItem:
    severity = _SEV_MAP.get((m.get("Severity") or "unknown").lower(), "info")
    title = m.get("Title") or m.get("ID") or "Trivy misconfiguration"
    return NormalizedItem(
        asset_value=target,
        asset_type=_pkg_kind(target),
        title=title[:400],
        description=(
            f"{m.get('Description') or ''}\n\n"
            f"Resolution: {m.get('Resolution') or '-'}"
        ).strip(),
        severity=severity,
        plugin="trivy",
        plugin_id=m.get("ID") or None,
        cwe_id=None,
        references=list(m.get("References", []) or []),
        extra={
            "type": m.get("Type"),
            "target": target,
            "cause": m.get("CauseMetadata"),
        },
    )


def parse(blob: bytes) -> list[NormalizedItem]:
    data = json.loads(blob)
    items: list[NormalizedItem] = []
    artifact = data.get("ArtifactName") or "trivy-target"
    for result in data.get("Results", []) or []:
        target = result.get("Target") or artifact
        for v in result.get("Vulnerabilities", []) or []:
            items.append(_vuln_to_item(target, v))
        for m in result.get("Misconfigurations", []) or []:
            items.append(_misconfig_to_item(target, m))
        for s in result.get("Secrets", []) or []:
            sev = _SEV_MAP.get((s.get("Severity") or "unknown").lower(), "info")
            items.append(NormalizedItem(
                asset_value=target,
                asset_type=_pkg_kind(target),
                title=s.get("Title") or s.get("RuleID") or "Trivy secret",
                description=(
                    f"Rule: {s.get('RuleID') or '-'}\n"
                    f"Match: {s.get('Match') or '-'}\n\n"
                    f"{s.get('Description') or ''}"
                ).strip(),
                severity=sev,
                plugin="trivy",
                plugin_id=s.get("RuleID"),
                extra={"category": s.get("Category"), "target": target},
            ))
    return items


def detect(filename: str, head: bytes) -> bool:
    n = filename.lower()
    if "trivy" in n:
        return True
    if n.endswith(".json"):
        try:
            data = json.loads(head if head else b"")
        except Exception:
            return False
        if not isinstance(data, dict):
            return False
        if "ArtifactName" in data and isinstance(data.get("Results"), list):
            return True
    return False
