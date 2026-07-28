"""SARIF 2.1.0 parser.

SARIF is the universal interchange format used by GitHub Code Scanning,
Semgrep, Snyk, Checkmarx, CodeQL, Trivy, kube-bench, and dozens of
other tools. We normalise the result list to NormalizedItem.

Each `result` becomes one item. The rule's `id` is the plugin_id, the
rule's `shortDescription` (or `fullDescription`/`name`) is the title,
and `message.text` is the description.

Severity resolution (first non-null wins):
  1. result.level            (error|warning|note|none)
  2. rule.properties["security-severity"]  (CVSS-like, 0.0–10.0)
  3. rule.defaultConfiguration.level
  4. "medium" fallback
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.ingestion.nessus import NormalizedItem


_LEVEL_MAP = {
    "error": "high",
    "warning": "medium",
    "note": "low",
    "none": "info",
}

_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}")
_CWE_RE = re.compile(r"CWE-\d+", re.IGNORECASE)


def _severity_from_level(level: str | None) -> str | None:
    if not level:
        return None
    return _LEVEL_MAP.get(level.lower())


def _severity_from_security_severity(score: Any) -> str | None:
    try:
        s = float(score)
    except (TypeError, ValueError):
        return None
    if s >= 9.0:
        return "critical"
    if s >= 7.0:
        return "high"
    if s >= 4.0:
        return "medium"
    if s > 0.0:
        return "low"
    return "info"


def _severity(result: dict, rule: dict | None) -> str:
    lvl = _severity_from_level(result.get("level"))
    if lvl:
        return lvl
    props = (rule or {}).get("properties") or {}
    ss = _severity_from_security_severity(props.get("security-severity"))
    if ss:
        return ss
    default_cfg = (rule or {}).get("defaultConfiguration") or {}
    lvl = _severity_from_level(default_cfg.get("level"))
    if lvl:
        return lvl
    return "medium"


def _coerce_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        return node.get("text") or ""
    return str(node)


def _rule_index(runs: list[dict]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for run in runs:
        tool = run.get("tool", {}).get("driver", {})
        for rule in tool.get("rules", []) or []:
            rid = rule.get("id")
            if rid and rid not in idx:
                idx[rid] = rule
    return idx


def parse(blob: bytes) -> list[NormalizedItem]:
    data = json.loads(blob)
    runs = data.get("runs", []) or []
    rule_idx = _rule_index(runs)
    items: list[NormalizedItem] = []
    for run in runs:
        for r in run.get("results", []) or []:
            rid = r.get("ruleId") or ""
            rule = rule_idx.get(rid, {}) if rid else {}
            sev = _severity(r, rule)
            title = (
                _coerce_text((rule.get("shortDescription") if rule else None))
                or _coerce_text((rule.get("fullDescription") if rule else None))
                or _coerce_text(rule.get("name"))
                or rid
                or "SARIF result"
            )
            message = _coerce_text(r.get("message"))
            location = ""
            for loc in r.get("locations", []) or []:
                pl = loc.get("physicalLocation", {}) or {}
                art = pl.get("artifactLocation", {}) or {}
                if art.get("uri"):
                    location = str(art["uri"])
                    break
            asset = location or "code"
            refs: list[str] = []
            for tx in r.get("taxa", []) or []:
                if isinstance(tx, dict) and tx.get("id"):
                    refs.append(str(tx["id"]))
            full_desc = message or title
            cve_match = _CVE_RE.search(full_desc) or _CVE_RE.search(title)
            cwe_match = _CWE_RE.search(full_desc) or _CWE_RE.search(title)
            items.append(NormalizedItem(
                asset_value=asset,
                asset_type="repo",
                title=title[:400],
                description=full_desc,
                severity=sev,
                cve_id=cve_match.group(0).upper() if cve_match else None,
                cwe_id=cwe_match.group(0).upper() if cwe_match else None,
                plugin="sarif",
                plugin_id=rid or None,
                references=refs,
                evidence=location,
                extra={
                    "level": r.get("level"),
                    "rule_index": r.get("ruleIndex"),
                    "kind": r.get("kind"),
                    "tool": (run.get("tool", {}).get("driver", {}) or {}).get("name"),
                },
            ))
    return items


def detect(filename: str, head: bytes) -> bool:
    n = filename.lower()
    if n.endswith(".sarif") or n.endswith(".sarif.json"):
        return True
    try:
        data = json.loads(head if head else b"")
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    schema = data.get("$schema") or ""
    if "sarif" in schema.lower():
        return True
    if isinstance(data.get("runs"), list) and data["runs"]:
        run0 = data["runs"][0]
        if isinstance(run0, dict) and isinstance(run0.get("tool"), dict):
            return True
    return False
