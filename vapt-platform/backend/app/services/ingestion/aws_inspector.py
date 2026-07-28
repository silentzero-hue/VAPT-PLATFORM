"""AWS Inspector findings JSON parser.

AWS Inspector's "describe-findings" output is a flat list of finding
objects. The newer `get-findings` response wraps them in
`{"findings": [...]}`. Both shapes are accepted.
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
    "informational": "info",
    "info": "info",
    "untriaged": "info",
}

_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)


def _walk(data: Any) -> list[dict]:
    if isinstance(data, dict) and isinstance(data.get("findings"), list):
        return [d for d in data["findings"] if isinstance(d, dict)]
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    return []


def _asset(f: dict) -> tuple[str, int | None, str]:
    attrs = f.get("assetAttributes") or {}
    agent_attrs = f.get("agentAttributes") or {}
    pkg_attrs = f.get("packageVulnerabilityDetails") or {}
    candidates = [
        attrs.get("hostname"),
        attrs.get("amiId"),
        attrs.get("ec2InstanceId"),
        attrs.get("ecrImageDigest"),
        attrs.get("lambdaFunctionName"),
        agent_attrs.get("hostname"),
    ]
    asset = next((c for c in candidates if c), "aws-inspector")
    port = None
    if isinstance(attrs.get("networkInterfaces"), list) and attrs["networkInterfaces"]:
        for ni in attrs["networkInterfaces"]:
            if isinstance(ni, dict) and ni.get("port"):
                try:
                    port = int(ni["port"])
                except (TypeError, ValueError):
                    port = None
                break
    asset_type = "host"
    if "ecrImageDigest" in attrs:
        asset_type = "container"
    elif "lambdaFunctionName" in attrs:
        asset_type = "function"
    return str(asset), port, asset_type


def parse(blob: bytes) -> list[NormalizedItem]:
    data = json.loads(blob)
    items: list[NormalizedItem] = []
    for f in _walk(data):
        sev_raw = (f.get("severity") or "info").lower()
        severity = _SEV_MAP.get(sev_raw, "info")
        asset, port, asset_type = _asset(f)
        title = f.get("title") or f.get("type") or "AWS Inspector finding"
        cve_id = None
        cve_list = []
        for v in f.get("vulnerabilities", []) or []:
            if isinstance(v, str):
                m = _CVE_RE.search(v)
                if m:
                    cve_list.append(m.group(0).upper())
        if cve_list:
            cve_id = cve_list[0]
        description_parts = [f.get("description") or ""]
        if f.get("remediation", {}).get("recommendation"):
            description_parts.append("Recommendation:\n" + str(f["remediation"]["recommendation"]))
        items.append(NormalizedItem(
            asset_value=asset,
            asset_type=asset_type,
            port=port,
            protocol="tcp" if port else None,
            title=title[:400],
            description="\n\n".join(p for p in description_parts if p) or title,
            severity=severity,
            cve_id=cve_id,
            plugin="aws_inspector",
            plugin_id=f.get("id") or f.get("findingArn"),
            evidence=(str(f.get("evidence"))[:4000] if f.get("evidence") else None),
            extra={
                "type": f.get("type"),
                "arn": f.get("findingArn"),
                "aws_account": f.get("awsAccountId"),
                "region": f.get("region"),
                "cve_list": cve_list,
            },
        ))
    return items


def detect(filename: str, head: bytes) -> bool:
    n = filename.lower()
    if "inspector" in n and "aws" in n:
        return True
    if not n.endswith(".json"):
        return False
    try:
        data = json.loads(head if head else b"")
    except Exception:
        return False
    findings = None
    if isinstance(data, dict) and isinstance(data.get("findings"), list):
        findings = data["findings"]
    elif isinstance(data, list):
        findings = data
    if not findings or not isinstance(findings[0], dict):
        return False
    first = findings[0]
    if "assetAttributes" in first or ("service" in first and "title" in first):
        return True
    return False
