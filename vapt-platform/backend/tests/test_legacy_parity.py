"""Tests for the legacy-tool-parity features: port extraction, RHEL
regex, multi-scan analyzer, table view, legacy DB import."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.asset import Asset
from app.models.engagement import Engagement, EngagementStatus, EngagementType
from app.models.finding import Finding
from app.models.user import Role, User, WorkspaceMembership
from app.models.vulnerability import Vulnerability
from app.models.workspace import Workspace
from app.services.legacy_db import _row_to_normalized, read_legacy_db
from app.services.multi_scan import ScanFingerprint, _triples
from app.services.port_extraction import (
    SERVICE_TO_PORT, canonical_port_string, extract_port,
)
from app.services.reporting.table_view import (
    build_table_view, render_table_view_docx, render_table_view_html,
)
from app.services.rhel_regex import (
    extract_advisory_id, filter_by_package, is_rhel_advisory,
    parse_package_info,
)


# ---------------------------------------------------------------------------
# Port extraction
# ---------------------------------------------------------------------------

class TestPortExtraction:
    def test_basic_int(self):
        assert extract_port(443) == (443, "tcp")

    def test_basic_str(self):
        assert extract_port("443/tcp") == (443, "tcp")

    def test_bare_number(self):
        assert extract_port("80") == (80, "tcp")

    def test_service_name(self):
        assert extract_port("https") == (443, "tcp")
        assert extract_port("ssh") == (22, "tcp")
        assert extract_port("DNS") == (53, "tcp")  # case insensitive

    def test_protocol_first(self):
        assert extract_port("tcp/443") == (443, "tcp")

    def test_general_tcp_is_zero(self):
        # Nessus "general/tcp" means "all ports" — represented as 0
        assert extract_port("general/tcp") == (0, "tcp")

    def test_range(self):
        assert extract_port("443-445") == (443, "tcp")

    def test_empty(self):
        assert extract_port("") == (None, None)
        assert extract_port(None) == (None, None)
        assert extract_port("N/A") == (None, None)

    def test_canonical(self):
        assert canonical_port_string(443, "tcp") == "443/tcp"
        assert canonical_port_string(None, None) == ""


# ---------------------------------------------------------------------------
# RHEL regex
# ---------------------------------------------------------------------------

class TestRhelRegex:
    def test_extract_rhsa(self):
        assert extract_advisory_id("Update per RHSA-2024:1234") == "RHSA-2024:1234"

    def test_extract_rhba(self):
        assert extract_advisory_id("see RHBA-2024:5678") == "RHBA-2024:5678"

    def test_extract_rhevsa(self):
        assert extract_advisory_id("RHEVSA-2024-0001") == "RHEVSA-2024:0001"

    def test_extract_none(self):
        assert extract_advisory_id("no advisory here") is None
        assert extract_advisory_id("") is None

    def test_parse_package_info(self):
        info = parse_package_info("Update openssl-1:1.0.2k-26.el7 to fix CVE-2024-001")
        assert info is not None
        assert info["package"] == "openssl"
        assert "1.0.2k-26.el7" in info["version"]

    def test_parse_rhel_advisory_only(self):
        info = parse_package_info("See RHSA-2024:9999 for details")
        assert info is not None
        assert info["advisory"] == "RHSA-2024:9999"

    def test_filter_by_package(self):
        vulns = [
            {"name": "openssl vuln", "remediation": "Update openssl-1:1.0.2k-26.el7"},
            {"name": "kernel vuln", "remediation": "Update kernel-3.10.0-1160.el7"},
            {"name": "no rhel", "remediation": "update your software"},
        ]
        out = filter_by_package(vulns, "kernel")
        assert len(out) == 1
        assert out[0]["_parsed"]["package"] == "kernel"

    def test_is_rhel_advisory(self):
        assert is_rhel_advisory("RHSA-2024:1234")
        assert not is_rhel_advisory("CVE-2024-1234")


# ---------------------------------------------------------------------------
# Multi-scan analyzer
# ---------------------------------------------------------------------------

def test_triples_from_findings():
    f1 = Finding(vulnerability_id=uuid.uuid4(), asset_id=uuid.uuid4(), port=443)
    f2 = Finding(vulnerability_id=uuid.uuid4(), asset_id=uuid.uuid4(), port=443)
    s = _triples([f1, f2])
    assert len(s) == 1  # dedup by (vuln, asset, port)


def test_scan_fingerprint_dataclass():
    sf = ScanFingerprint(
        scan_id="x", name="t", created_at="2024",
        finished_at=None, triple_count=0,
    )
    assert sf.triples == set()
    assert sf.findings == []


# ---------------------------------------------------------------------------
# Table view
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_table_view_groups_by_severity(db):
    ws = Workspace(name="T", slug=f"t-{uuid.uuid4().hex[:6]}")
    db.add(ws); await db.flush()
    e = Engagement(
        workspace_id=ws.id, code="E1", name="E1", client="A",
        type=EngagementType.WEBAPP, status=EngagementStatus.ACTIVE,
        methodology="OWASP-WSTG",
    )
    db.add(e); await db.flush()
    v = Vulnerability(
        workspace_id=ws.id, title="CVE-2024-001 Log4Shell",
        description="x", severity="critical", cvss_score=10.0,
        fingerprint_hash=uuid.uuid4().hex,
    )
    db.add(v); await db.flush()
    a = Asset(workspace_id=ws.id, type="ip", value="10.0.0.1",
              first_seen=datetime.now(timezone.utc),
              last_seen=datetime.now(timezone.utc))
    db.add(a); await db.flush()
    f = Finding(workspace_id=ws.id, engagement_id=e.id,
                vulnerability_id=v.id, asset_id=a.id, port=443)
    db.add(f); await db.flush()

    data = await build_table_view(db, e.id)
    assert data["by_severity"]["Critical"][0]["title"] == "CVE-2024-001 Log4Shell"
    assert data["by_severity"]["Critical"][0]["host_count"] == 1
    assert 443 in data["by_severity"]["Critical"][0]["port_list"]


def test_render_table_view_docx_is_valid():
    data = {
        "engagement": {"code": "E1", "name": "E1", "client": "A"},
        "by_severity": {
            "Critical": [{
                "cve_id": "CVE-2024-001", "title": "Test",
                "cvss_score": 10.0, "host_count": 3,
                "host_list": ["10.0.0.1", "10.0.0.2", "10.0.0.3"],
                "port_list": [443, 80], "sample_asset": "10.0.0.1",
                "occurrence_count": 3,
            }],
            "High": [],
            "Medium": [], "Low": [], "Informational": [],
        },
        "totals": {"Critical": 1, "High": 0, "Medium": 0, "Low": 0, "Informational": 0},
    }
    b = render_table_view_docx(data)
    assert b.startswith(b"PK")  # docx is a zip


def test_render_table_view_html_contains_table():
    data = {
        "engagement": {"code": "E", "name": "E", "client": "A"},
        "by_severity": {
            "Critical": [],
            "High": [{
                "cve_id": "CVE-2024-002", "title": "XSS",
                "cvss_score": 8.0, "host_count": 1,
                "host_list": ["web1"], "port_list": [443],
                "sample_asset": "web1", "occurrence_count": 1,
            }],
            "Medium": [], "Low": [], "Informational": [],
        },
        "totals": {"Critical": 0, "High": 1, "Medium": 0, "Low": 0, "Informational": 0},
    }
    h = render_table_view_html(data)
    assert "CVE-2024-002" in h
    assert "XSS" in h
    assert "class='high'" in h  # the heading


# ---------------------------------------------------------------------------
# Legacy DB import
# ---------------------------------------------------------------------------

def _make_legacy_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE vulnerabilities (
            id INTEGER PRIMARY KEY,
            name TEXT, host TEXT, port TEXT, plugin_id TEXT, cve TEXT,
            severity TEXT, description TEXT, solution TEXT,
            scan_id INTEGER, scan_name TEXT,
            first_seen TEXT, last_seen TEXT
        );
    """)
    rows = [
        (1, "Log4Shell", "10.0.0.1", "443/tcp", "156000", "CVE-2021-44228",
         "Critical", "RCE via JNDI", "Upgrade log4j",
         100, "scan1", "2024-01-01", "2024-01-01"),
        (2, "OpenSSL EOL", "10.0.0.1", "443/tcp", "100000", "",
         "High", "old", "Upgrade", 100, "scan1", "2024-01-01", "2024-01-01"),
        (3, "OpenSSL EOL", "10.0.0.2", "443/tcp", "100000", "",
         "High", "old", "Upgrade", 100, "scan1", "2024-01-01", "2024-01-01"),
    ]
    con.executemany(
        "INSERT INTO vulnerabilities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows,
    )
    con.commit()
    con.close()


class TestLegacyDb:
    def test_read_legacy_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            _make_legacy_db(path)
            items = read_legacy_db(path)
            assert len(items) == 3
            assert items[0].title == "Log4Shell"
            assert items[0].port == 443
            assert items[0].protocol == "tcp"
            assert items[0].cve_id == "CVE-2021-44228"
            assert items[0].severity == "critical"
        finally:
            os.unlink(path)

    def test_read_legacy_db_missing_table(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            with pytest.raises(RuntimeError, match="missing"):
                read_legacy_db(path)
        finally:
            os.unlink(path)

    def test_row_to_normalized_skips_empty(self):
        # missing name → None
        assert _row_to_normalized({"name": "", "host": "x", "port": "80"}) is None
        # severity mapping
        item = _row_to_normalized({
            "name": "x", "host": "h", "port": "443", "severity": "Critical",
            "cve": "CVE-2024-1", "plugin_id": "1",
        })
        assert item is not None
        assert item.severity == "critical"


# ---------------------------------------------------------------------------
# Nessus API client (signature only — we don't have a Nessus server in CI)
# ---------------------------------------------------------------------------

def test_nessus_client_builds_headers():
    from app.services.nessus_api.client import NessusClient
    c = NessusClient(
        base_url="https://localhost:8834",
        access_key="abc", secret_key="def",
    )
    assert "accessKey=abc" in c._headers["X-ApiKeys"]
    assert "secretKey=def" in c._headers["X-ApiKeys"]
    # base url normalized
    assert c.base_url == "https://localhost:8834"
    c2 = NessusClient(
        base_url="https://localhost:8834/",
        access_key="a", secret_key="b",
    )
    assert c2.base_url == "https://localhost:8834"  # trailing slash removed
