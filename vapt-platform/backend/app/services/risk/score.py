"""Risk score: composite of severity, asset criticality, EPSS, KEV.

Formula (default; configurable per workspace):
  risk = clamp(0..100,
      0.30 * severity_component(severity)
    + 0.25 * criticality_component(asset.criticality)
    + 0.25 * epss_component(epss_score)  # 0..1 → 0..1
    + 0.20 * kev_boost(kev_listed)
  )

  severity_component: critical=1.0, high=0.75, medium=0.5, low=0.25, info=0.05
  criticality_component: critical=1.0, high=0.75, medium=0.5, low=0.25
  kev_boost: 1.0 if kev_listed else 0.0
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

SEVERITY_COMPONENT = {
    "critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25, "info": 0.05,
}
CRITICALITY_COMPONENT = {
    "critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25,
}


@dataclass
class RiskComponents:
    severity: float
    criticality: float
    epss: float
    kev_boost: float
    cvss: float
    recency: float  # how recent the finding is (older = slightly less risk)
    base: float
    final: float

    def to_dict(self) -> dict:
        return {
            "severity": round(self.severity, 3),
            "criticality": round(self.criticality, 3),
            "epss": round(self.epss, 3),
            "kev_boost": round(self.kev_boost, 3),
            "cvss": round(self.cvss, 3),
            "recency": round(self.recency, 3),
            "base": round(self.base, 3),
            "final": round(self.final, 3),
        }


def compute_risk(
    *,
    severity: str,
    asset_criticality: str,
    cvss_score: float | None,
    epss_score: float | None,
    kev_listed: bool,
    age_days: float | None = None,
    weights: dict | None = None,
) -> RiskComponents:
    sev = SEVERITY_COMPONENT.get(severity, 0.5)
    crit = CRITICALITY_COMPONENT.get(asset_criticality, 0.5)
    epss = max(0.0, min(1.0, epss_score or 0.0))
    kev = 1.0 if kev_listed else 0.0
    # CVSS (0..10) normalized to 0..1, weight lower when EPSS already covers it
    cvss = (cvss_score or 0.0) / 10.0
    # Recency: 1.0 if <7d, 0.7 if 7-30d, 0.5 if 30-90d, 0.3 older
    if age_days is None:
        recency = 1.0
    elif age_days < 7:
        recency = 1.0
    elif age_days < 30:
        recency = 0.85
    elif age_days < 90:
        recency = 0.65
    else:
        recency = 0.4

    w = weights or {
        "severity": 0.30, "criticality": 0.20, "epss": 0.20, "kev": 0.20, "cvss": 0.10,
    }
    base = (
        w["severity"] * sev
        + w["criticality"] * crit
        + w["epss"] * epss
        + w["kev"] * kev
        + w["cvss"] * cvss
    )
    final = max(0.0, min(100.0, base * 100 * recency))
    return RiskComponents(
        severity=sev, criticality=crit, epss=epss, kev_boost=kev,
        cvss=cvss, recency=recency, base=base, final=final,
    )
