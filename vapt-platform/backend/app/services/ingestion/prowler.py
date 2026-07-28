"""Prowler JSON parser (AWS security checks).

Prowler output is a flat array of finding objects, or a wrapper
`{"findings": [...]}`. Each finding has `Service`, `ResourceArn`,
`Severity`, `CheckTitle`, and a `Description`.
"""

from __future__ import annotations

import json
from typing import Any

from app.services.ingestion.nessus import NormalizedItem


_SEV_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "informational": "info",
    "info": "info",
    "informational_low": "low",
    "informational_medium": "medium",
    "informational_high": "high",
    "informational_critical": "critical",
}


def _walk_findings(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("findings"), list):
            return [d for d in data["findings"] if isinstance(d, dict)]
        if isinstance(data.get("Results"), list):
            return [d for d in data["Results"] if isinstance(d, dict)]
    return []


def _asset_from_resource(resource: str) -> tuple[str, str]:
    """Prowler resources are ARNs like `arn:aws:s3:::bucket-name`."""
    if not resource:
        return "aws-unknown", "cloud"
    if resource.startswith("arn:aws:"):
        parts = resource.split(":", 5)
        service = parts[2] if len(parts) > 2 else "aws"
        # the trailing piece is "service:region:account:resource"
        tail = parts[5] if len(parts) > 5 else resource
        return f"{service}:{tail}" or "aws-unknown", "cloud"
    return resource, "cloud"


def parse(blob: bytes) -> list[NormalizedItem]:
    data = json.loads(blob)
    items: list[NormalizedItem] = []
    for f in _walk_findings(data):
        sev_raw = (f.get("Severity") or f.get("severity") or "info").lower()
        severity = _SEV_MAP.get(sev_raw, "info")
        service = f.get("Service") or "aws"
        resource = f.get("ResourceArn") or f.get("Resource") or service
        asset_value, asset_type = _asset_from_resource(resource)
        title = f.get("CheckTitle") or f.get("CheckID") or "Prowler finding"
        desc_parts = []
        if (d := f.get("Description")):
            desc_parts.append(str(d))
        if (r := f.get("Risk")):
            desc_parts.append("Risk:\n" + str(r))
        if (rem := f.get("Remediation", {}).get("Recommendation")):
            if isinstance(rem, dict):
                rem_txt = rem.get("Text") or ""
                rem_url = rem.get("Url") or ""
                if rem_txt:
                    desc_parts.append("Remediation:\n" + str(rem_txt))
                if rem_url:
                    desc_parts.append("More info: " + str(rem_url))
        check_id = f.get("CheckID") or f.get("check_id")
        items.append(NormalizedItem(
            asset_value=asset_value,
            asset_type=asset_type,
            title=f"{service}: {title}"[:400],
            description="\n\n".join(desc_parts) or title,
            severity=severity,
            plugin="prowler",
            plugin_id=check_id,
            evidence=f.get("Status") or f.get("status"),
            extra={
                "service": service,
                "region": f.get("Region"),
                "account": f.get("AccountID") or f.get("AccountId"),
                "check_id": check_id,
                "compliance": f.get("Compliance"),
                "status": f.get("Status"),
            },
        ))
    return items


def detect(filename: str, head: bytes) -> bool:
    n = filename.lower()
    if "prowler" in n:
        return True
    if not n.endswith(".json"):
        return False
    try:
        data = json.loads(head if head else b"")
    except Exception:
        return False
    findings = None
    if isinstance(data, dict):
        if isinstance(data.get("findings"), list):
            findings = data["findings"]
    elif isinstance(data, list):
        findings = data
    if not findings or not isinstance(findings[0], dict):
        return False
    first = findings[0]
    return ("CheckID" in first and "Service" in first) or ("CheckID" in first and "ResourceArn" in first)
