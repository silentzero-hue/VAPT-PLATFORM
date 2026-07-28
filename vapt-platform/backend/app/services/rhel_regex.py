"""RHEL / Red Hat security advisory parser.

Nessus plugins for RHEL often report findings whose remediation is
expressed as a RHSA / RHBA / RHEVSA id, sometimes with the exact
package list to upgrade. The legacy tool had `test_parse_rhel_package_info`
and `test_filter_rhel_by_package` — so we need the same primitives:

  1. Extract the advisory id from a finding's text:
       "Red Hat Security Advisory: RHSA-2024:1234"
       "RHSA-2024:1234"
       "RHBA-2024:5678"
       "RHEVSA-2024-0001"
  2. Filter vulnerabilities by package (e.g. "is kernel affected?").
  3. Parse the affected package list from a remediation string:
       "Update to version 2.14.0-1.el9 or later"
       "Update openssl-1:1.0.2k-19.el7 to 1:1.0.2k-26.el7"
"""

from __future__ import annotations

import re
from typing import Any

ADV_RE = re.compile(r"\b(RHSA|RHBA|RHEVSA|RHEA)-\d{4}:(\d{4,7})\b", re.IGNORECASE)

PKG_UPDATE_RE = re.compile(
    r"(?:Update|Upgrade)\s+(?:to\s+)?"
    r"(?:([\w.+-]+?))?\s*"
    r"([\w.+-]+?):?([\w.+-]+?)?"
    r"-\s*(\d[\w.+~:-]*)\s*"
    r"(?:or later|or newer)?",
    re.IGNORECASE,
)


def extract_advisory_id(text: str | None) -> str | None:
    if not text:
        return None
    m = ADV_RE.search(text)
    return m.group(0).upper() if m else None


def parse_package_info(text: str | None) -> dict[str, Any] | None:
    """Return {"advisory": "RHSA-...", "package": "openssl", "epoch": "1",
              "version": "1.0.2k-26.el7"} or None."""
    if not text:
        return None
    adv = extract_advisory_id(text)
    m = PKG_UPDATE_RE.search(text)
    if not m:
        return {"advisory": adv} if adv else None
    name = m.group(2) or m.group(1)
    epoch = m.group(3)
    version = m.group(4)
    if not name or not version:
        return {"advisory": adv} if adv else None
    return {
        "advisory": adv,
        "package": name,
        "epoch": epoch,
        "version": version,
    }


def filter_by_package(vulns: list[dict], package_substr: str) -> list[dict]:
    """Legacy `test_filter_rhel_by_package` parity.

    Each `vuln` is a dict that may carry a `description` and a `remediation`
    field. We return those whose remediation text contains a parseable
    RHEL package update for the given package substring."""
    out = []
    for v in vulns:
        info = parse_package_info(v.get("remediation") or v.get("description") or "")
        if not info:
            continue
        name = info.get("package") or ""
        if package_substr.lower() in name.lower():
            out.append({**v, "_parsed": info})
    return out


def is_rhel_advisory(text: str | None) -> bool:
    return extract_advisory_id(text) is not None
