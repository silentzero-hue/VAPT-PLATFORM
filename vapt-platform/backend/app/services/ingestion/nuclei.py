"""Nuclei JSONL output parser.

Nuclei writes one JSON object per line. Each line is an independent
finding with `info` (template metadata) and `matched-at` (the URL/host
where it matched). A "line" may span multiple physical lines if the
JSON contains a newline inside a string, but in practice Nuclei emits
one compact object per line.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable
from urllib.parse import urlparse

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


def _iter_lines(blob: bytes) -> Iterable[dict]:
    for line in blob.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield obj


def _split_host_port(matched_at: str) -> tuple[str, int | None, str | None, str | None]:
    """Best-effort host/port extraction from a Nuclei matched-at URL."""
    if not matched_at:
        return "unknown", None, None, None
    if "://" in matched_at:
        try:
            u = urlparse(matched_at)
        except ValueError:
            return matched_at, None, None, None
        host = u.hostname or matched_at
        port = u.port
        scheme = u.scheme
        path = u.path or None
        return host, port, scheme, path
    return matched_at, None, None, None


def _classification_fields(blob: dict) -> tuple[str | None, str | None, float | None, str | None]:
    info = blob.get("info", {}) or {}
    classification = info.get("classification", {}) or {}
    cve_id = None
    cwe_id = None
    if isinstance(classification.get("cve-id"), list):
        ids = classification["cve-id"]
        if ids:
            cve_id = str(ids[0]).strip().upper()
    elif isinstance(classification.get("cve-id"), str):
        cve_id = classification["cve-id"].strip().upper()
    cwe_raw = classification.get("cwe-id")
    if isinstance(cwe_raw, list) and cwe_raw:
        cwe_id = f"CWE-{cwe_raw[0]}" if not str(cwe_raw[0]).upper().startswith("CWE-") else str(cwe_raw[0]).upper()
    elif isinstance(cwe_raw, str) and cwe_raw.strip():
        cwe_id = cwe_raw if cwe_raw.upper().startswith("CWE-") else f"CWE-{cwe_raw}"
    cvss = classification.get("cvss-score")
    cvss_score = None
    try:
        if cvss is not None:
            cvss_score = float(cvss)
    except (TypeError, ValueError):
        cvss_score = None
    cvss_vec = classification.get("cvss-metrics") or classification.get("cvss-vector")
    return cve_id, cwe_id, cvss_score, cvss_vec


def parse(blob: bytes) -> list[NormalizedItem]:
    items: list[NormalizedItem] = []
    for entry in _iter_lines(blob):
        info = entry.get("info", {}) or {}
        severity_raw = (info.get("severity") or "info").lower()
        severity = _SEV_MAP.get(severity_raw, "info")
        name = info.get("name") or "Nuclei finding"
        description = info.get("description") or name
        matched_at = entry.get("matched-at") or entry.get("matched") or ""
        host, port, scheme, path = _split_host_port(matched_at)
        template_id = entry.get("template-id") or info.get("template-id") or ""
        template_type = entry.get("type") or info.get("type")
        cve_id, cwe_id, cvss_score, cvss_vec = _classification_fields(entry)
        refs: list[str] = []
        for ref in (info.get("reference") or []):
            if isinstance(ref, str):
                refs.append(ref)
        tags = info.get("tags") or ""
        items.append(NormalizedItem(
            asset_value=host,
            asset_type="host",
            port=port,
            protocol=scheme or ("tcp" if port else None),
            title=name[:400],
            description=description[:8000],
            severity=severity,
            cve_id=cve_id,
            cwe_id=cwe_id,
            plugin="nuclei",
            plugin_id=template_id or None,
            references=refs,
            evidence=entry.get("extracted-results") or entry.get("curl-output"),
            extra={
                "type": template_type,
                "tags": tags.split(",") if isinstance(tags, str) else tags,
                "path": path,
                "matched": matched_at,
                "cvss_score": cvss_score,
                "cvss_vector": cvss_vec,
            },
        ))
    return items


def detect(filename: str, head: bytes) -> bool:
    n = filename.lower()
    if "nuclei" in n:
        return True
    if n.endswith(".jsonl"):
        first = head.split(b"\n", 1)[0].strip()
        try:
            obj = json.loads(first)
        except Exception:
            return False
        if not isinstance(obj, dict):
            return False
        if "template-id" in obj or "matched-at" in obj:
            return True
        info = obj.get("info") if isinstance(obj, dict) else None
        if isinstance(info, dict) and ("name" in info and "severity" in info):
            return True
    return False
