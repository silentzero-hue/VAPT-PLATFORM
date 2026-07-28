"""Agent improvement loop: capture diffs between AI draft and final
approved text, compute similarity, build the few-shot corpus for
future runs, and surface per-analyst stats.
"""

from __future__ import annotations

import difflib
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentDraftDiff
from app.models.vulnerability import Vulnerability


def _similarity(a: str | None, b: str | None) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


async def record_diff(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    vulnerability_id: uuid.UUID,
    agent_session_id: str,
    engagement_id: uuid.UUID | None,
    reviewer_id: uuid.UUID,
    decision: str,  # approved|changes_requested|rejected
    original_impact: str | None,
    final_impact: str | None,
    original_recommendation: str | None,
    final_recommendation: str | None,
    edit_seconds: int | None = None,
) -> AgentDraftDiff:
    diff = AgentDraftDiff(
        workspace_id=workspace_id,
        vulnerability_id=vulnerability_id,
        agent_session_id=agent_session_id,
        engagement_id=engagement_id,
        reviewer_id=reviewer_id,
        decision=decision,
        original_impact=original_impact,
        final_impact=final_impact,
        original_recommendation=original_recommendation,
        final_recommendation=final_recommendation,
        impact_similarity=_similarity(original_impact, final_impact),
        recommendation_similarity=_similarity(original_recommendation, final_recommendation),
        edit_seconds=edit_seconds,
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(diff)
    await db.flush()
    return diff


async def per_analyst_stats(
    db: AsyncSession, workspace_id: uuid.UUID, *, days: int = 30
) -> list[dict]:
    """Per-analyst approval rate + average edit similarity in the last N days."""
    since = datetime.now(timezone.utc).timestamp() - days * 86400
    rows = (await db.execute(
        select(
            AgentDraftDiff.reviewer_id,
            AgentDraftDiff.decision,
            func.count(AgentDraftDiff.id),
            func.avg(AgentDraftDiff.impact_similarity),
            func.avg(AgentDraftDiff.recommendation_similarity),
        )
        .where(
            AgentDraftDiff.workspace_id == workspace_id,
            AgentDraftDiff.reviewed_at >= datetime.fromtimestamp(since, tz=timezone.utc),
        )
        .group_by(AgentDraftDiff.reviewer_id, AgentDraftDiff.decision)
    )).all()
    by_user: dict[uuid.UUID, dict] = {}
    for reviewer_id, decision, n, imp, rec in rows:
        u = by_user.setdefault(reviewer_id or uuid.UUID(int=0), {
            "reviewer_id": str(reviewer_id) if reviewer_id else None,
            "approved": 0, "changes_requested": 0, "rejected": 0,
            "avg_impact_similarity": 0.0, "avg_recommendation_similarity": 0.0,
        })
        u[decision] = (u.get(decision) or 0) + n
        if imp is not None:
            u["avg_impact_similarity"] = float(imp)
        if rec is not None:
            u["avg_recommendation_similarity"] = float(rec)
    return list(by_user.values())


async def few_shot_corpus(
    db: AsyncSession, workspace_id: uuid.UUID, *, max_examples: int = 3
) -> list[dict]:
    """Top approved, high-similarity pairs the agent can use as examples."""
    rows = (await db.execute(
        select(AgentDraftDiff, Vulnerability)
        .join(Vulnerability, Vulnerability.id == AgentDraftDiff.vulnerability_id)
        .where(
            AgentDraftDiff.workspace_id == workspace_id,
            AgentDraftDiff.decision == "approved",
            AgentDraftDiff.impact_similarity.is_not(None),
        )
        .order_by(AgentDraftDiff.impact_similarity.asc())  # lowest similarity = highest learning
        .limit(max_examples)
    )).all()
    return [
        {
            "vuln_title": v.title,
            "vuln_description": v.description,
            "ai_impact": d.original_impact,
            "final_impact": d.final_impact,
            "ai_recommendation": d.original_recommendation,
            "final_recommendation": d.final_recommendation,
        }
        for d, v in rows
    ]
