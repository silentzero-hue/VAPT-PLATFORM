"""Parser tests — one per supported format.

Each test:
  * has a small representative sample blob (inline literal)
  * asserts `parse()` returns at least one NormalizedItem with the
    expected severity
  * asserts `detect()` returns the right format

These tests do NOT touch the database. They exercise the parsers
in isolation, which is the part that is the highest regression risk.
"""

from __future__ import annotations

import json

import pytest

from app.models.ingestion import IngestionFormat
from app.services.ingestion.formats import detect_format
from app.services.ingestion.nessus import NormalizedItem


# ---------------------------------------------------------------------------
# Burp Suite
# ---------------------------------------------------------------------------

BURP_XML = b"""<?xml version="1.0"?>
<issues burpVersion="2024.1" exportTime="Mon Jan 01 00:00:00 UTC 2024">
  <issue>
    <type>1234567</type>
    <name>SQL injection</name>
    <host>https://example.com</host>
    <hostip>10.0.0.5</hostip>
    <port>443</port>
    <ssl>true</ssl>
    <location>/login.php?id=</location>
    <severity>High</severity>
    <confidence>Certain</confidence>
    <issueBackground>Input is concatenated into a SQL query.</issueBackground>
    <remediationBackground>Use parameterised queries.</remediationBackground>
  </issue>
  <issue>
    <type>2222222</type>
    <name>Cookie without Secure flag</name>
    <host>https://example.com</host>
    <port>443</port>
    <severity>Low</severity>
    <location>/</location>
  </issue>
</issues>"""


def test_burp_parser():
    from app.services.ingestion import burp
    items = burp.parse(BURP_XML)
    assert len(items) == 2
    assert items[0].title == "SQL injection"
    assert items[0].severity == "high"
    assert items[0].asset_value == "10.0.0.5"
    assert items[0].port == 443
    assert items[0].plugin == "burp"
    assert items[0].plugin_id == "burp:1234567"
    assert items[1].severity == "low"
    assert detect_format("scan.xml", BURP_XML[:256]) == IngestionFormat.BURP


# ---------------------------------------------------------------------------
# OWASP ZAP
# ---------------------------------------------------------------------------

ZAP_XML = b"""<?xml version="1.0"?>
<OWASPZAPReport version="2.14" generated="Mon, 01 Jan 2024 00:00:00">
  <site name="https://example.com" host="example.com" port="443" ssl="true">
    <alerts>
      <alertitem>
        <pluginid>10202</pluginid>
        <alert>Absence of Anti-CSRF Tokens</alert>
        <name>Absence of Anti-CSRF Tokens</name>
        <riskcode>2</riskcode>
        <confidence>2</confidence>
        <riskdesc>Medium (Medium)</riskdesc>
        <desc>No Anti-CSRF tokens were found in a HTML submission form.</desc>
        <uri>https://example.com/login</uri>
        <method>POST</method>
        <param>csrf</param>
        <evidence>&lt;input type=&quot;hidden&quot; name=&quot;csrf&quot;&gt;</evidence>
        <cweid>352</cweid>
        <solution>Use a tested CSRF library for the framework in use.</solution>
      </alertitem>
      <alertitem>
        <pluginid>10063</pluginid>
        <alert>Permissions Policy Header Not Set</alert>
        <name>Permissions Policy Header Not Set</name>
        <riskcode>3</riskcode>
        <riskdesc>High (Medium)</riskdesc>
        <uri>https://example.com/</uri>
      </alertitem>
    </alerts>
  </site>
</OWASPZAPReport>"""


def test_zap_parser():
    from app.services.ingestion import zap
    items = zap.parse(ZAP_XML)
    assert len(items) == 2
    assert items[0].severity == "medium"
    assert items[0].plugin == "zap"
    assert items[0].plugin_id == "10202"
    assert items[1].severity == "high"
    assert detect_format("zap.xml", ZAP_XML[:256]) == IngestionFormat.ZAP


# ---------------------------------------------------------------------------
# SARIF
# ---------------------------------------------------------------------------

SARIF_JSON = json.dumps({
    "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
    "version": "2.1.0",
    "runs": [
        {
            "tool": {"driver": {"name": "semgrep", "rules": [
                {
                    "id": "python.lang.security.audit.eval",
                    "shortDescription": {"text": "Detected use of eval()"},
                    "defaultConfiguration": {"level": "error"},
                }
            ]}},
            "results": [
                {
                    "ruleId": "python.lang.security.audit.eval",
                    "ruleIndex": 0,
                    "level": "error",
                    "message": {"text": "eval() called on user input (CVE-2024-9999)."},
                    "locations": [{"physicalLocation": {"artifactLocation": {"uri": "app/views.py"}}}],
                }
            ],
        }
    ],
}).encode()


def test_sarif_parser():
    from app.services.ingestion import sarif
    items = sarif.parse(SARIF_JSON)
    assert len(items) == 1
    assert items[0].severity == "high"
    assert items[0].plugin == "sarif"
    assert items[0].plugin_id == "python.lang.security.audit.eval"
    assert items[0].cve_id == "CVE-2024-9999"
    assert items[0].asset_value == "app/views.py"
    assert detect_format("results.sarif", SARIF_JSON[:256]) == IngestionFormat.SARIF


# ---------------------------------------------------------------------------
# Nuclei
# ---------------------------------------------------------------------------

NUCLEI_JSONL = "\n".join([
    json.dumps({
        "template-id": "http-exposures/log4j",
        "info": {
            "name": "Apache Log4j RCE",
            "severity": "critical",
            "description": "JNDI lookup in log4j < 2.17.0",
            "reference": ["https://logging.apache.org"],
            "classification": {
                "cve-id": ["CVE-2021-44228"],
                "cwe-id": ["CWE-502"],
                "cvss-score": 10.0,
            },
            "tags": "log4j,rce,cve",
        },
        "type": "http",
        "matched-at": "https://example.com:443/login",
        "extracted-results": "jndi:ldap://attacker/x",
    }),
    json.dumps({
        "template-id": "tech-detect/nginx",
        "info": {"name": "Nginx detected", "severity": "info"},
        "type": "tech-detect",
        "matched-at": "http://10.0.0.5:80",
    }),
]).encode() + b"\n"


def test_nuclei_parser():
    from app.services.ingestion import nuclei
    items = nuclei.parse(NUCLEI_JSONL)
    assert len(items) == 2
    assert items[0].severity == "critical"
    assert items[0].cve_id == "CVE-2021-44228"
    assert items[0].cwe_id == "CWE-502"
    assert items[0].port == 443
    assert items[0].plugin_id == "http-exposures/log4j"
    assert items[1].severity == "info"
    assert detect_format("findings.jsonl", NUCLEI_JSONL[:256]) == IngestionFormat.NUCLEI


# ---------------------------------------------------------------------------
# OpenVAS
# ---------------------------------------------------------------------------

OPENVAS_XML = b"""<?xml version="1.0"?>
<report>
  <results>
    <result id="r1">
      <host>10.0.0.1</host>
      <port>443/tcp</port>
      <threat>High</threat>
      <name>OpenSSL 1.0.1 Heartbleed</name>
      <description>OpenSSL is vulnerable to Heartbleed (CVE-2014-0160).</description>
      <nvt oid="1.3.6.1.4.1.25623.1.0.103441">
        <name>OpenSSL 1.0.1 Heartbleed</name>
        <cve>CVE-2014-0160</cve>
        <refs>
          <ref type="url" id="https://www.openssl.org/news/secadv/20140407.txt"/>
        </refs>
      </nvt>
    </result>
    <result id="r2">
      <host>10.0.0.2</host>
      <port>general/tcp</port>
      <threat>Log</threat>
      <name>ICMP reachable</name>
    </result>
  </results>
</report>"""


def test_openvas_parser():
    from app.services.ingestion import openvas
    items = openvas.parse(OPENVAS_XML)
    assert len(items) == 2
    assert items[0].severity == "high"
    assert items[0].cve_id == "CVE-2014-0160"
    assert items[0].port == 443
    assert items[0].asset_type == "ip"
    assert items[1].severity == "info"  # "log" maps to info
    assert detect_format("openvas.xml", OPENVAS_XML[:256]) == IngestionFormat.OPENVAS


# ---------------------------------------------------------------------------
# Trivy
# ---------------------------------------------------------------------------

TRIVY_JSON = json.dumps({
    "ArtifactName": "nginx:1.14",
    "Results": [
        {
            "Target": "nginx:1.14 (debian 9.13)",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2021-23017",
                    "PkgName": "libc6",
                    "InstalledVersion": "2.24-11+deb9u4",
                    "FixedVersion": "2.28-10",
                    "Severity": "HIGH",
                    "Title": "libc: DNS response poisoning",
                    "Description": "A flaw was found in libc.",
                    "CweIDs": ["CWE-331"],
                    "References": ["https://example.com/cve"],
                }
            ],
            "Misconfigurations": [
                {
                    "ID": "DS001",
                    "Type": "Dockerfile Security Check",
                    "Title": "Specify a tag in the FROM statement",
                    "Severity": "MEDIUM",
                    "Description": "When using a FROM statement you should use a specific tag.",
                    "Resolution": "Add a tag to the FROM statement.",
                }
            ],
        }
    ],
}).encode()


def test_trivy_parser():
    from app.services.ingestion import trivy
    items = trivy.parse(TRIVY_JSON)
    assert len(items) == 2
    assert items[0].severity == "high"
    assert items[0].cve_id == "CVE-2021-23017"
    assert items[0].plugin_id == "CVE-2021-23017"
    assert items[1].severity == "medium"
    assert items[1].plugin_id == "DS001"
    assert detect_format("trivy.json", TRIVY_JSON[:256]) == IngestionFormat.TRIVY


# ---------------------------------------------------------------------------
# Snyk
# ---------------------------------------------------------------------------

SNYK_JSON = json.dumps({
    "vulnerabilities": [
        {
            "id": "SNYK-PYTHON-LOG4J-1234",
            "title": "Remote Code Execution",
            "packageName": "log4j",
            "version": "2.14.0",
            "fixedIn": ["2.17.0"],
            "severity": "critical",
            "identifiers": {"CVE": ["CVE-2021-44228"], "CWE": ["CWE-502"]},
            "description": "RCE via JNDI lookup.",
            "references": [{"url": "https://snyk.io/vuln/SNYK-PYTHON-LOG4J-1234"}],
        }
    ]
}).encode()


def test_snyk_parser():
    from app.services.ingestion import snyk
    items = snyk.parse(SNYK_JSON)
    assert len(items) == 1
    assert items[0].severity == "critical"
    assert items[0].cve_id == "CVE-2021-44228"
    assert items[0].plugin_id == "SNYK-PYTHON-LOG4J-1234"
    assert detect_format("snyk.json", SNYK_JSON[:256]) == IngestionFormat.SNYK


# ---------------------------------------------------------------------------
# Prowler
# ---------------------------------------------------------------------------

PROWLER_JSON = json.dumps([
    {
        "CheckID": "s3_bucket_public_access",
        "CheckTitle": "Check if S3 buckets have public access block enabled",
        "Service": "s3",
        "Severity": "high",
        "ResourceArn": "arn:aws:s3:::my-public-bucket",
        "Region": "us-east-1",
        "Status": "FAIL",
        "Description": "S3 bucket has public access enabled.",
        "Risk": "Public buckets may leak data.",
        "Remediation": {
            "Recommendation": {"Text": "Enable Block Public Access.", "Url": "https://aws.amazon.com/"}
        },
    }
]).encode()


def test_prowler_parser():
    from app.services.ingestion import prowler
    items = prowler.parse(PROWLER_JSON)
    assert len(items) == 1
    assert items[0].severity == "high"
    assert items[0].plugin_id == "s3_bucket_public_access"
    assert "s3:my-public-bucket" in items[0].asset_value
    assert detect_format("prowler.json", PROWLER_JSON[:256]) == IngestionFormat.PROWLER


# ---------------------------------------------------------------------------
# testssl
# ---------------------------------------------------------------------------

TESTSSL_JSON = json.dumps({
    "findings": [
        {
            "id": "heartbleed",
            "ip": "10.0.0.5",
            "port": 443,
            "severity": "high",
            "finding": "TLS heartbeat extension is enabled (CVE-2014-0160).",
            "cve": "CVE-2014-0160",
        },
        {
            "id": "self_signed_cert",
            "ip": "10.0.0.5",
            "port": 443,
            "severity": "info",
            "finding": "Self-signed certificate.",
        }
    ]
}).encode()


def test_testssl_parser():
    from app.services.ingestion import testssl
    items = testssl.parse(TESTSSL_JSON)
    assert len(items) == 2
    assert items[0].severity == "high"
    assert items[0].cve_id == "CVE-2014-0160"
    assert items[0].port == 443
    assert items[1].severity == "info"
    assert detect_format("testssl.json", TESTSSL_JSON[:256]) == IngestionFormat.TESTSSL


# ---------------------------------------------------------------------------
# WPScan
# ---------------------------------------------------------------------------

WPSCAN_JSON = json.dumps({
    "target_url": "https://wp.example.com",
    "scan_aborted": False,
    "version": {"number": "5.8.2", "status": "insecure"},
    "findings": {
        "wp-version-5.8.2": {
            "title": "WordPress 5.8.2",
            "description": "Outdated version.",
            "severity": "low",
            "confirmed": True,
            "type": "version",
        }
    },
    "interesting_findings": {
        "wp-readme": {
            "title": "WordPress readme.html found",
            "description": "Exposes WordPress version.",
            "type": "info",
        }
    },
}).encode()


def test_wpscan_parser():
    from app.services.ingestion import wpscan
    items = wpscan.parse(WPSCAN_JSON)
    assert len(items) >= 2
    by_title = {i.title: i for i in items}
    assert "WordPress 5.8.2" in by_title
    assert by_title["WordPress 5.8.2"].severity == "low"
    assert any("WordPress readme.html" in t for t in by_title)
    assert detect_format("wpscan.json", WPSCAN_JSON[:256]) == IngestionFormat.WPSCAN


# ---------------------------------------------------------------------------
# Nikto
# ---------------------------------------------------------------------------

NIKTO_CSV = (
    b'"ip","port","hostname","method","uri","http_code","osvdb_id","message"\r\n'
    b'"10.0.0.5","443","example.com","GET","/admin/","403","3092","/admin/ accessible but forbidden."\r\n'
    b'"10.0.0.5","80","example.com","GET","/server-status","200","1","Apache server-status exposed."\r\n'
)


def test_nikto_csv_parser():
    from app.services.ingestion import nikto
    items = nikto.parse(NIKTO_CSV)
    assert len(items) == 2
    assert items[0].severity == "info"
    assert items[0].asset_value == "10.0.0.5"
    assert items[0].port == 443
    assert items[0].plugin_id == "osvdb-3092"
    assert detect_format("nikto.csv", NIKTO_CSV[:256]) == IngestionFormat.NIKTO


NIKTO_JSON = json.dumps({
    "vulnerabilities": [
        {
            "ip": "10.0.0.5", "port": 80, "uri": "/",
            "message": "Anti-clickjacking header missing",
            "osvdb_id": "12345",
        }
    ]
}).encode()


def test_nikto_json_parser():
    from app.services.ingestion import nikto
    items = nikto.parse(NIKTO_JSON)
    assert len(items) == 1
    assert items[0].plugin_id == "osvdb-12345"
    assert detect_format("nikto.json", NIKTO_JSON[:256]) == IngestionFormat.NIKTO


# ---------------------------------------------------------------------------
# Metasploit
# ---------------------------------------------------------------------------

METASPLOIT_XML = b"""<?xml version="1.0"?>
<MetasploitV5>
  <vulns>
    <vuln>
      <host>10.0.0.5</host>
      <port>445</port>
      <service>smb</service>
      <name>MS17-010 EternalBlue</name>
      <module>exploit/windows/smb/ms17_010_eternalblue</module>
      <info>
        <description>Remote code execution via SMBv1.</description>
        <cvss>9.3</cvss>
        <refs>
          <ref>CVE-2017-0144</ref>
        </refs>
      </info>
    </vuln>
  </vulns>
  <notes>
    <note type="vuln">
      <host>10.0.0.6</host>
      <port>22</port>
      <module>auxiliary/scanner/ssh/ssh_login</module>
      <data>Weak credentials detected.</data>
    </note>
  </notes>
</MetasploitV5>"""


def test_metasploit_parser():
    from app.services.ingestion import metasploit
    items = metasploit.parse(METASPLOIT_XML)
    assert len(items) == 2
    assert items[0].severity == "critical"  # cvss 9.3
    assert items[0].cve_id == "CVE-2017-0144"
    assert items[0].plugin_id == "exploit/windows/smb/ms17_010_eternalblue"
    assert items[1].severity == "info"
    assert detect_format("msf.xml", METASPLOIT_XML[:256]) == IngestionFormat.METASPLOIT


# ---------------------------------------------------------------------------
# AWS Inspector
# ---------------------------------------------------------------------------

AWS_INSPECTOR_JSON = json.dumps({
    "findings": [
        {
            "id": "arn:aws:inspector2:us-east-1:111:package/CVE-2022-1234",
            "title": "CVE-2022-1234 openssl",
            "severity": "high",
            "type": "PACKAGE_VULNERABILITY",
            "assetAttributes": {"hostname": "ip-10-0-0-5", "amiId": "ami-abc"},
            "vulnerabilities": ["CVE-2022-1234"],
            "description": "Outdated openssl.",
            "remediation": {"recommendation": "Update openssl to 3.0.7."},
        }
    ]
}).encode()


def test_aws_inspector_parser():
    from app.services.ingestion import aws_inspector
    items = aws_inspector.parse(AWS_INSPECTOR_JSON)
    assert len(items) == 1
    assert items[0].severity == "high"
    assert items[0].cve_id == "CVE-2022-1234"
    assert items[0].asset_value == "ip-10-0-0-5"
    assert detect_format("inspector.json", AWS_INSPECTOR_JSON[:512]) == IngestionFormat.AWS_INSPECTOR


# ---------------------------------------------------------------------------
# kube-bench
# ---------------------------------------------------------------------------

KUBE_BENCH_JSON = json.dumps({
    "Controls": [
        {
            "id": "1.1",
            "text": "Master Node Configuration Files",
            "tests": [
                {
                    "id": "1.1.1",
                    "desc": "Ensure that the API server pod specification file permissions are set to 644 or more restrictive",
                    "results": [
                        {"status": "FAIL", "cause": "permissions are 666"},
                        {"status": "PASS"},
                    ],
                },
                {
                    "id": "1.1.2",
                    "desc": "Ensure that the API server pod specification file ownership is set to root:root",
                    "results": [
                        {"status": "WARN", "cause": "owner is 1000"},
                    ],
                },
            ],
        }
    ]
}).encode()


def test_kube_bench_parser():
    from app.services.ingestion import kube_bench
    items = kube_bench.parse(KUBE_BENCH_JSON)
    assert len(items) == 2
    # The PASS result is filtered out, so we get the FAIL and the WARN.
    severities = sorted([i.severity for i in items])
    assert severities == ["high", "medium"]
    assert all(i.asset_type == "cluster" for i in items)
    assert detect_format("kube-bench.json", KUBE_BENCH_JSON[:256]) == IngestionFormat.KUBE_BENCH


# ---------------------------------------------------------------------------
# Qualys (detected by table but no spec parser; we add a minimal one)
# ---------------------------------------------------------------------------

QUALYS_XML = b"""<?xml version="1.0"?>
<WAS_SCAN_REPORT>
  <VULNERABILITY>
    <QID>150001</QID>
    <TITLE>SSL Certificate - Self-Signed</TITLE>
    <SEVERITY>2</SEVERITY>
    <HOST>10.0.0.5</HOST>
    <PORT>443</PORT>
    <CVE_ID>CVE-2014-0160</CVE_ID>
    <DIAGNOSIS>Self-signed certificate detected.</DIAGNOSIS>
    <SOLUTION>Use a CA-signed certificate.</SOLUTION>
  </VULNERABILITY>
</WAS_SCAN_REPORT>"""


def test_qualys_parser():
    from app.services.ingestion import qualys
    items = qualys.parse(QUALYS_XML)
    assert len(items) == 1
    assert items[0].severity == "low"  # "2" in qualys is severity level 2 of 5
    assert detect_format("qualys.xml", QUALYS_XML[:256]) == IngestionFormat.QUALYS


# ---------------------------------------------------------------------------
# Format detector edge cases
# ---------------------------------------------------------------------------

def test_detect_returns_unknown_for_garbage():
    assert detect_format("random.bin", b"\x00\x01\x02 not a real file") == IngestionFormat.UNKNOWN


def test_detect_filename_hints_work():
    # A name hint is enough for SARIF (extension-based).
    assert detect_format("report.sarif", b"{}") == IngestionFormat.SARIF
    assert detect_format("image.cdx.json", b"{}") == IngestionFormat.CYCLONEDX
    assert detect_format("image.spdx.json", b"{}") == IngestionFormat.SPDX


# ---------------------------------------------------------------------------
# NormalizedItem shape regression (don't let parsers drift the schema)
# ---------------------------------------------------------------------------

def test_normalized_item_fields_present():
    from app.services.ingestion import burp
    items = burp.parse(BURP_XML)
    it: NormalizedItem = items[0]
    for f in (
        "asset_value", "asset_type", "port", "protocol", "title",
        "description", "severity", "cve_id", "cwe_id", "plugin",
        "plugin_id", "references", "evidence", "raw", "extra",
    ):
        assert hasattr(it, f), f"NormalizedItem missing {f}"
    assert it.severity in ("critical", "high", "medium", "low", "info")
