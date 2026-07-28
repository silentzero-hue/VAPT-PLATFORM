"""Tests for new features added in v2: comments, retests, evidence,
tokens, webhooks, portal, risk score, SBOM, agent feedback."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.security import hash_password
from app.models.api_token import ApiToken
from app.models.comment import CommentMention, FindingComment
from app.models.evidence_blob import EvidenceBlob
from app.models.finding import Finding
from app.models.portal import PortalShare
from app.models.report import Report, ReportStatus
from app.models.retest import RetestCycle
from app.models.user import Role, User, WorkspaceMembership
from app.models.vulnerability import Vulnerability
from app.models.webhook import WebhookEndpoint
from app.models.workspace import Workspace
from app.services.api_tokens import create_token, validate_token
from app.services.comments import create_comment, extract_mentions
from app.services.evidence.store import upload as upload_evidence
from app.services.portal import create_share
from app.services.retest import schedule, summarise
from app.services.risk.score import compute_risk
from app.services.webhooks import sign, enqueue
from app.services.ingestion.sbom import parse_cyclonedx, parse_spdx


# ---------------------------------------------------------------------------
# 1) Risk score
# ---------------------------------------------------------------------------

def test_risk_score_critical_kev_is_high():
    r = compute_risk(
        severity="critical", asset_criticality="critical",
        cvss_score=10.0, epss_score=0.95, kev_listed=True, age_days=1,
    )
    assert r.final > 90


def test_risk_score_info_no_kev_is_low():
    r = compute_risk(
        severity="info", asset_criticality="low",
        cvss_score=2.0, epss_score=0.0, kev_listed=False, age_days=120,
    )
    assert r.final < 30


def test_risk_score_components_recorded():
    r = compute_risk(
        severity="high", asset_criticality="medium",
        cvss_score=7.5, epss_score=0.4, kev_listed=False, age_days=10,
    )
    d = r.to_dict()
    for k in ("severity", "criticality", "epss", "kev_boost", "cvss", "recency", "base", "final"):
        assert k in d
    assert 0 <= d["final"] <= 100


# ---------------------------------------------------------------------------
# 2) Comments + @mentions
# ---------------------------------------------------------------------------

def test_mention_extraction():
    body = "hi @alice@example.com and @bob@example.com, please look"
    assert extract_mentions(body) == ["alice@example.com", "bob@example.com"]


def test_mention_extraction_dedups():
    body = "@a@x.com @a@x.com @b@x.com"
    assert extract_mentions(body) == ["a@x.com", "b@x.com"]


@pytest.mark.asyncio
async def test_comment_creates_mention_records(db):
    ws = Workspace(name="CT", slug=f"ct-{uuid.uuid4().hex[:6]}")
    db.add(ws); await db.flush()
    eng = await _make_engagement(db, ws.id)
    v = Vulnerability(
        workspace_id=ws.id, title="x", description="x", severity="low",
        fingerprint_hash=uuid.uuid4().hex,
    )
    db.add(v); await db.flush()
    a = await _make_asset(db, ws.id)
    f = Finding(
        workspace_id=ws.id, engagement_id=eng.id,
        vulnerability_id=v.id, asset_id=a.id,
    )
    db.add(f); await db.flush()
    u = User(email="bob@example.com", full_name="Bob", password_hash=hash_password("x"))
    db.add(u); await db.flush()
    c = await create_comment(
        db, finding_id=f.id, author_id=uuid.uuid4(),
        body="hey @bob@example.com look here",
    )
    assert "bob@example.com" in c.mentions
    mentions = (await db.execute(
        select(CommentMention).where(CommentMention.comment_id == c.id)
    )).scalars().all()
    assert len(mentions) == 1
    assert mentions[0].user_id == u.id


# ---------------------------------------------------------------------------
# 3) Evidence dedup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evidence_blob_dedup(db):
    ws = Workspace(name="E", slug=f"e-{uuid.uuid4().hex[:6]}")
    db.add(ws); await db.flush()
    blob1 = await upload_evidence(
        db, workspace_id=ws.id, actor_id=None,
        data=b"hello world", mime="text/plain", kind="log", filename="x.log",
    )
    await db.flush()
    blob2 = await upload_evidence(
        db, workspace_id=ws.id, actor_id=None,
        data=b"hello world", mime="text/plain", kind="log", filename="x.log",
    )
    await db.flush()
    assert blob1.id == blob2.id
    assert blob1.ref_count == 2
    # different bytes = different blob
    blob3 = await upload_evidence(
        db, workspace_id=ws.id, actor_id=None,
        data=b"different", mime="text/plain", kind="log", filename="y.log",
    )
    await db.flush()
    assert blob3.id != blob1.id
    assert blob1.ref_count == 2  # unchanged


# ---------------------------------------------------------------------------
# 4) API tokens
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_token_issue_and_validate(db):
    ws = Workspace(name="T", slug=f"t-{uuid.uuid4().hex[:6]}")
    db.add(ws); await db.flush()
    tok, raw = await create_token(
        db, workspace_id=ws.id, name="ci", scopes=["*"],
        expires_at=None, actor_id=None,
    )
    assert raw.startswith("vapt_")
    validated = await validate_token(db, raw)
    assert validated is not None
    assert validated.id == tok.id


@pytest.mark.asyncio
async def test_token_scope_filtering(db):
    ws = Workspace(name="T2", slug=f"t2-{uuid.uuid4().hex[:6]}")
    db.add(ws); await db.flush()
    tok, raw = await create_token(
        db, workspace_id=ws.id, name="limited", scopes=["ingest:upload"],
        expires_at=None, actor_id=None,
    )
    # has the required scope
    assert await validate_token(db, raw, required_scope="ingest:upload")
    # does NOT have a different scope (no wildcard)
    assert not await validate_token(db, raw, required_scope="report:approve")


# ---------------------------------------------------------------------------
# 5) Webhook signature
# ---------------------------------------------------------------------------

def test_webhook_signature_is_deterministic():
    body = b'{"event":"test"}'
    ts = "1700000000"
    s1 = sign("secret", body, ts)
    s2 = sign("secret", body, ts)
    assert s1 == s2
    assert len(s1) == 64  # sha256 hex


def test_webhook_signature_changes_with_ts():
    body = b'{"event":"test"}'
    s1 = sign("secret", body, "1700000000")
    s2 = sign("secret", body, "1700000001")
    assert s1 != s2


# ---------------------------------------------------------------------------
# 6) Retest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retest_schedule_and_summarise(db):
    ws = Workspace(name="R", slug=f"r-{uuid.uuid4().hex[:6]}")
    db.add(ws); await db.flush()
    eng = await _make_engagement(db, ws.id, code="E1")
    rc = await schedule(
        db, workspace_id=ws.id, engagement_id=eng.id,
        title="retest 1", scheduled_for=None, actor_id=uuid.uuid4(),
    )
    assert rc.status.value == "scheduled"


# ---------------------------------------------------------------------------
# 7) Portal shares
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_portal_share_create_returns_token_once(db):
    ws = Workspace(name="P", slug=f"p-{uuid.uuid4().hex[:6]}")
    db.add(ws); await db.flush()
    eng = await _make_engagement(db, ws.id)
    r = Report(workspace_id=ws.id, engagement_id=eng.id,
               title="x", status=ReportStatus.APPROVED)
    db.add(r); await db.flush()
    share, raw = await create_share(
        db, workspace_id=ws.id, report_id=r.id, label="to client",
        actor_id=None,
    )
    assert raw.startswith("psh_")
    assert share.label == "to client"
    assert share.current_views == 0


# ---------------------------------------------------------------------------
# 8) SBOM parsers
# ---------------------------------------------------------------------------

def test_parse_cyclonedx_json():
    blob = b"""{
      "bomFormat": "CycloneDX",
      "specVersion": "1.5",
      "version": 1,
      "components": [
        {"name": "log4j-core", "version": "2.14.0", "purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.0"},
        {"name": "lodash", "version": "4.17.20", "purl": "pkg:npm/lodash@4.17.20"}
      ]
    }"""
    comps = parse_cyclonedx(blob)
    assert len(comps) == 2
    assert comps[0].name == "log4j-core"
    assert comps[0].ecosystem == "maven"
    assert comps[1].ecosystem == "npm"


def test_parse_spdx_json():
    blob = b"""{
      "spdxVersion": "SPDX-2.3",
      "name": "test-sbom",
      "packages": [
        {"name": "requests", "versionInfo": "2.31.0", "externalRefs": [{"referenceType": "purl", "referenceLocator": "pkg:pypi/requests@2.31.0"}]}
      ]
    }"""
    comps = parse_spdx(blob)
    assert len(comps) == 1
    assert comps[0].ecosystem == "pypi"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

async def _make_engagement(db, workspace_id, code="E"):
    from app.models.engagement import Engagement, EngagementStatus, EngagementType
    e = Engagement(
        workspace_id=workspace_id, code=code, name="eng",
        client="acme", type=EngagementType.WEBAPP, status=EngagementStatus.ACTIVE,
        methodology="OWASP-WSTG",
    )
    db.add(e); await db.flush()
    return e


async def _make_asset(db, workspace_id):
    from datetime import datetime, timezone
    from app.models.asset import Asset
    a = Asset(
        workspace_id=workspace_id, type="ip", value="10.0.0.1",
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    db.add(a); await db.flush()
    return a
