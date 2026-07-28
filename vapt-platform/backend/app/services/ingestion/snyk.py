"""Snyk JSON (`snyk test --json`) parser.

The payload is wrapped in `{"vulnerabilities": [...]}`. Each entry is
a single finding with CVE/CVSS/remediation metadata. We also support
the multi-document `--all-projects` output which nests `runs`.
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


def _walk_vulns(data: Any) -> list[dict]:
    """Snyk has a few shapes — top-level `vulnerabilities`, or `runs[*].results.vulnerabilities`."""
    out: list[dict] = []
    if isinstance(data, dict):
        if isinstance(data.get("vulnerabilities"), list):
            out.extend(data["vulnerabilities"])
        for run in data.get("runs", []) or []:
            res = run.get("results") if isinstance(run, dict) else None
            if isinstance(res, dict):
                if isinstance(res.get("vulnerabilities"), list):
                    out.extend(res["vulnerabilities"])
    return out


def _to_severity(v: dict) -> str:
    sev = (v.get("severity") or v.get("priority") or "").lower()
    mapped = _SEV_MAP.get(sev)
    if mapped:
        return mapped
    cvss = v.get("cvssScore")
    if cvss is None:
        return "medium"
    try:
        s = float(cvss)
    except (TypeError, ValueError):
        return "medium"
    if s >= 9.0:
        return "critical"
    if s >= 7.0:
        return "high"
    if s >= 4.0:
        return "medium"
    if s > 0.0:
        return "low"
    return "info"


def _vuln_to_item(v: dict) -> NormalizedItem:
    cve_ids = v.get("identifiers", {}).get("CVE") or []
    cve_id = None
    if isinstance(cve_ids, list) and cve_ids:
        m = _CVE_RE.search(str(cve_ids[0]))
        cve_id = m.group(0).upper() if m else str(cve_ids[0]).upper()
    cwe_ids = v.get("identifiers", {}).get("CWE") or []
    cwe_id = None
    if isinstance(cwe_ids, list) and cwe_ids:
        first = str(cwe_ids[0])
        cwe_id = first if first.upper().startswith("CWE-") else f"CWE-{first}"
    refs: list[str] = []
    for ref in v.get("references", []) or []:
        if isinstance(ref, dict) and ref.get("url"):
            refs.append(ref["url"])
        elif isinstance(ref, str):
            refs.append(ref)
    pkg = v.get("packageName") or "package"
    title = v.get("title") or v.get("id") or "Snyk vulnerability"
    asset = v.get("from") or v.get("targetFile") or pkg
    return NormalizedItem(
        asset_value=asset,
        asset_type="package",
        title=f"{pkg}: {title}"[:400],
        description=(
            f"Package: {pkg}\n"
            f"Version: {v.get('version') or '-'}\n"
            f"Fixed in: {(v.get('fixedIn') or ['-'])[0] if isinstance(v.get('fixedIn'), list) else v.get('fixedIn') or '-'}\n"
            f"Snyk ID: {v.get('id') or '-'}\n\n"
            f"{v.get('description') or ''}"
        ).strip(),
        severity=_to_severity(v),
        cve_id=cve_id,
        cwe_id=cwe_id,
        plugin="snyk",
        plugin_id=v.get("id"),
        references=refs,
        evidence=v.get("proofOfConcept"),
        extra={
            "package": pkg,
            "version": v.get("version"),
            "fixed_in": v.get("fixedIn"),
            "exploit": v.get("exploit"),
            "target_file": v.get("targetFile"),
            "cvss_score": v.get("cvssScore"),
        },
    )


def parse(blob: bytes) -> list[NormalizedItem]:
    data = json.loads(blob)
    return [_vuln_to_item(v) for v in _walk_vulns(data)]


def detect(filename: str, head: bytes) -> bool:
    n = filename.lower()
    if "snyk" in n:
        return True
    if not n.endswith(".json"):
        return False
    try:
        data = json.loads(head if head else b"")
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    vulns = data.get("vulnerabilities")
    if not isinstance(vulns, list) or not vulns:
        return False
    first = vulns[0]
    if not isinstance(first, dict):
        return False
    if "packageName" in first and "identifiers" in first:
        return True
    return False
