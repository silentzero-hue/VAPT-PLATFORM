"""Fingerprinting + dedup engine.

Two layers:
 1. Exact match: SHA-256 over (workspace_id, cve_id|plugin_id, normalized title).
    O(1) lookup via DB unique constraint.
 2. Fuzzy match: pgvector cosine similarity over an embedding of
    (title + first 1500 chars of description). Auto-merge above a
    high-confidence threshold; flag for analyst in the middle band;
    create a new record below the lower threshold.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vulnerability import Vulnerability
from app.services.embeddings.service import embed_text

HIGH_CONFIDENCE = 0.93
REVIEW_BAND = 0.80


def _normalize_text(s: str) -> str:
    s = s or ""
    s = re.sub(r"https?://\S+", "", s)  # drop URLs
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-zA-Z0-9 ._-]", "", s)
    return s.strip().lower()


def compute_fingerprint(
    workspace_id: uuid.UUID,
    *,
    cve_id: str | None,
    plugin_id: str | None,
    title: str,
    asset_type: str | None = None,
    plugin: str | None = None,
) -> str:
    """Stable hash used as the exact-match dedup key.

    Per spec: same vuln on many hosts → one record. We key on
    (cve_id OR plugin_id, normalized title) inside a workspace, NOT on
    asset, port, or evidence — that would defeat the whole point.
    """
    cve_id = cve_id.upper() if cve_id else None
    if cve_id is None and plugin_id is None:
        key = f"{asset_type or 'na'}|{plugin or 'na'}|{_normalize_text(title)[:120]}"
    else:
        key = cve_id or plugin_id
    payload = f"{workspace_id}|{key}|{_normalize_text(title)}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _embedding_text(title: str, description: str) -> str:
    # used to compute embeddings
    return f"{_normalize_text(title)} || {_normalize_text(description)[:1500]}"


def fake_embedding(text_blob: str, dim: int = 384) -> list[float]:
    """Deterministic stand-in embedding for environments without an
    embedding model. Real deployments should call a model server
    (e.g. sentence-transformers, bge-small, or an external API) and
    replace this function.

    The interface is identical — swap the body, keep the signature.
    """
    digest = hashlib.sha512(text_blob.encode()).digest()
    out = []
    for i in range(dim):
        b = digest[i % len(digest)]
        out.append((b / 255.0) * 2 - 1)
    # L2 normalize
    norm = sum(x * x for x in out) ** 0.5 or 1.0
    return [x / norm for x in out]


@dataclass
class DedupResult:
    vulnerability: Vulnerability
    matched: bool
    via: str  # exact | fuzzy_high | fuzzy_review | new
    similarity: float | None = None


async def find_or_create(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    title: str,
    description: str,
    cve_id: str | None,
    cwe_id: str | None,
    plugin: str | None,
    plugin_id: str | None,
    severity: str,
    cvss_score: float | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[Vulnerability, bool, bool]:
    """Returns (vuln, created, requires_review).

    - created=True on a new row.
    - requires_review=True when a fuzzy match fell in the review band and
      the analyst should confirm the merge.
    """
    extra = extra or {}
    fp = compute_fingerprint(
        workspace_id,
        cve_id=cve_id, plugin_id=plugin_id, title=title,
        asset_type=extra.get("asset_type"), plugin=plugin,
    )

    # 1) Exact
    existing = await db.scalar(
        select(Vulnerability).where(
            Vulnerability.workspace_id == workspace_id,
            Vulnerability.fingerprint_hash == fp,
        )
    )
    if existing:
        existing.occurrence_count += 1
        if cvss_score is not None:
            if existing.cvss_score is None or cvss_score > existing.cvss_score:
                existing.cvss_score = cvss_score
        return existing, False, False
    # 2) Fuzzy via pgvector
    emb_text = _embedding_text(title, description)
    emb_list = embed_text(emb_text)
    # pgvector requires a string-formatted vector; raw SQL via asyncpg
    # doesn't auto-coerce a list to the Vector type.
    emb_str = "[" + ",".join(f"{x:.7f}" for x in emb_list) + "]"
    sims = (await db.execute(
        text(
            """
            SELECT id, 1 - (embedding <=> CAST(:emb AS vector)) AS sim
            FROM vulnerabilities
            WHERE workspace_id = :wid AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT 5
            """
        ),
        {"emb": emb_str, "wid": str(workspace_id)},
    )).all()
    if sims:
        best_id, best_sim = sims[0]
        if best_sim is not None and best_sim >= HIGH_CONFIDENCE:
            v = await db.get(Vulnerability, best_id)
            v.occurrence_count += 1
            return v, False, False

        if best_sim is not None and best_sim >= REVIEW_BAND:
            # create a new vuln but mark it for review (caller will queue)
            v = await _create(
                db, workspace_id=workspace_id, title=title, description=description,
                cve_id=cve_id, cwe_id=cwe_id, plugin=plugin, plugin_id=plugin_id,
                severity=severity, cvss_score=cvss_score, fingerprint=fp, embedding=emb_list, extra=extra,
            )
            v.extra["dedup_candidate_match_id"] = str(best_id)
            v.extra["dedup_candidate_similarity"] = float(best_sim)
            return v, True, True

    # 3) new
    v = await _create(
        db, workspace_id=workspace_id, title=title, description=description,
        cve_id=cve_id, cwe_id=cwe_id, plugin=plugin, plugin_id=plugin_id,
        severity=severity, cvss_score=cvss_score, fingerprint=fp, embedding=emb_list, extra=extra,
    )
    return v, True, False


async def _create(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    title: str, description: str,
    cve_id: str | None, cwe_id: str | None,
    plugin: str | None, plugin_id: str | None,
    severity: str, cvss_score: float | None,
    fingerprint: str, embedding: list[float],
    extra: dict,
) -> Vulnerability:
    v = Vulnerability(
        workspace_id=workspace_id,
        title=title, description=description,
        cve_id=cve_id, cwe_id=cwe_id,
        source_plugin=plugin, source_plugin_id=plugin_id,
        severity=severity,
        cvss_score=cvss_score,
        fingerprint_hash=fingerprint,
        embedding=embedding,
        extra=extra,
    )
    db.add(v)
    await db.flush()
    return v


async def similarity_search(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    title: str,
    description: str,
    threshold: float = 0.5,
) -> list[tuple[uuid.UUID, float]]:
    emb = fake_embedding(_embedding_text(title, description))
    rows = (await db.execute(
        text(
            """
            SELECT id, 1 - (embedding <=> :emb) AS sim
            FROM vulnerabilities
            WHERE workspace_id = :wid AND embedding IS NOT NULL
              AND 1 - (embedding <=> :emb) >= :thr
            ORDER BY sim DESC
            LIMIT 20
            """
        ),
        {"emb": emb, "wid": str(workspace_id), "thr": threshold},
    )).all()
    return [(r[0], float(r[1])) for r in rows]
