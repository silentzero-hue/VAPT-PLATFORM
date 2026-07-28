"""kube-bench JSON output parser.

kube-bench emits a structure with top-level `Controls` (uppercase
in newer versions) or `controls` (lowercase in older versions).
Each control has `id`, `tests`, and each test has `results` with
state (`PASS`/`FAIL`/`WARN`/`INFO`) and per-result details.
"""

from __future__ import annotations

import json
from typing import Any

from app.services.ingestion.nessus import NormalizedItem


_STATE_MAP = {
    "fail": "high",
    "warn": "medium",
    "warning": "medium",
    "pass": "info",
    "info": "info",
    "skip": "info",
}


def _walk(data: Any) -> tuple[list[dict], str | None]:
    if not isinstance(data, dict):
        return [], None
    controls = data.get("Controls") or data.get("controls") or []
    if not isinstance(controls, list):
        return [], None
    summary = data.get("Summary") or data.get("summary")
    if isinstance(summary, dict):
        summary = json.dumps(summary)
    return controls, summary


def _control_node_iter(controls: list[dict]):
    """Yield test_results and the surrounding control/test context."""
    for ctl in controls:
        if not isinstance(ctl, dict):
            continue
        ctl_id = ctl.get("id") or "kube-bench"
        ctl_text = ctl.get("text") or ctl.get("description") or ""
        for test in ctl.get("tests", []) or []:
            if not isinstance(test, dict):
                continue
            test_id = test.get("id") or ""
            test_desc = test.get("desc") or ""
            for r in test.get("results", []) or []:
                if not isinstance(r, dict):
                    continue
                yield ctl_id, ctl_text, test_id, test_desc, r


def parse(blob: bytes) -> list[NormalizedItem]:
    data = json.loads(blob)
    controls, _ = _walk(data)
    items: list[NormalizedItem] = []
    for ctl_id, ctl_text, test_id, test_desc, r in _control_node_iter(controls):
        state = (r.get("status") or r.get("state") or "info").lower()
        if state in ("pass",):
            # pass items are noise; skip
            continue
        severity = _STATE_MAP.get(state, "info")
        title = test_desc or ctl_text or f"kube-bench {ctl_id}.{test_id}"
        items.append(NormalizedItem(
            asset_value="kubernetes",
            asset_type="cluster",
            title=title[:400],
            description=(
                f"Control: {ctl_id} {ctl_text}\n"
                f"Test: {test_id} {test_desc}\n"
                f"State: {state}\n\n"
                f"{r.get('cause') or r.get('remediation') or r.get('info') or ''}"
            ).strip(),
            severity=severity,
            plugin="kube_bench",
            plugin_id=f"{ctl_id}.{test_id}",
            evidence=str(r.get("actual_value") or "")[:4000],
            extra={
                "control_id": ctl_id,
                "test_id": test_id,
                "state": state,
                "expected": r.get("expected_result"),
            },
        ))
    return items


def detect(filename: str, head: bytes) -> bool:
    n = filename.lower()
    if "kube-bench" in n or "kube_bench" in n:
        return True
    if not n.endswith(".json"):
        return False
    try:
        data = json.loads(head if head else b"")
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    if isinstance(data.get("Controls"), list) or isinstance(data.get("controls"), list):
        return True
    return False
