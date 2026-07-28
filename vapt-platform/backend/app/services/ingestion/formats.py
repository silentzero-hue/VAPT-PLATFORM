"""Format detection for scanner outputs.

A single function `detect_format` inspects the filename and the first
256 bytes of the file and returns the IngestionFormat. Order matters:
filename-based detection first, then content-based, with XML
disambiguators last (multiple tools produce XML).
"""

from __future__ import annotations

import json

from app.models.ingestion import IngestionFormat


def _sniff_json(head: bytes) -> dict | None:
    try:
        obj = json.loads(head)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def detect_format(filename: str, head: bytes) -> IngestionFormat:
    n = filename.lower()

    # --- explicit filename extensions ---------------------------------
    if n.endswith(".nessus") or n.endswith(".nessus.xml"):
        return IngestionFormat.NESSUS
    if n.endswith(".nessus_legacy") or n.endswith(".db"):
        return IngestionFormat.LEGACY_DB
    if n.endswith(".sarif") or n.endswith(".sarif.json"):
        return IngestionFormat.SARIF
    if n.endswith(".cdx.json") or n.endswith(".cyclonedx.json"):
        return IngestionFormat.CYCLONEDX
    if n.endswith(".spdx.json"):
        return IngestionFormat.SPDX
    if n.endswith(".jsonl") or n.endswith(".ndjson"):
        return IngestionFormat.NUCLEI  # most common JSONL for security

    # --- JSON content sniffing ---------------------------------------
    data = _sniff_json(head)
    if data is not None:
        schema = str(data.get("$schema") or "").lower()
        if "sarif" in schema:
            return IngestionFormat.SARIF
        if data.get("bomFormat") == "CycloneDX":
            return IngestionFormat.CYCLONEDX
        if data.get("spdxVersion"):
            return IngestionFormat.SPDX
        # Runs+tool.driver.name is the SARIF giveaway
        if isinstance(data.get("runs"), list) and data["runs"]:
            run0 = data["runs"][0]
            if isinstance(run0, dict) and isinstance(run0.get("tool"), dict):
                return IngestionFormat.SARIF
        # Trivy
        if isinstance(data.get("Results"), list) and "ArtifactName" in data:
            return IngestionFormat.TRIVY
        # Snyk
        if isinstance(data.get("vulnerabilities"), list) and data["vulnerabilities"]:
            v0 = data["vulnerabilities"][0]
            if isinstance(v0, dict) and "packageName" in v0 and "identifiers" in v0:
                return IngestionFormat.SNYK
        # WPScan
        if "target_url" in data and ("findings" in data or "interesting_findings" in data):
            return IngestionFormat.WPSCAN
        if "scan_aborted" in data:
            return IngestionFormat.WPSCAN
        # kube-bench
        if isinstance(data.get("Controls"), list) or isinstance(data.get("controls"), list):
            return IngestionFormat.KUBE_BENCH
        # AWS Inspector
        findings = data.get("findings")
        if isinstance(findings, list) and findings:
            v0 = findings[0]
            if isinstance(v0, dict) and ("assetAttributes" in v0 or "service" in v0):
                return IngestionFormat.AWS_INSPECTOR
        # Prowler
        if isinstance(findings, list) and findings:
            v0 = findings[0]
            if isinstance(v0, dict) and ("CheckID" in v0 or "check_id" in v0):
                return IngestionFormat.PROWLER
        # testssl
        if isinstance(findings, list) and findings:
            v0 = findings[0]
            if isinstance(v0, dict) and "finding" in v0 and "id" in v0 and ("ip" in v0 or "port" in v0):
                return IngestionFormat.TESTSSL

    # --- JSON list at top level (e.g. Prowler, AWS Inspector) --------
    try:
        arr = json.loads(head)
    except Exception:
        arr = None
    if isinstance(arr, list) and arr and isinstance(arr[0], dict):
        v0 = arr[0]
        if "CheckID" in v0 or "check_id" in v0:
            return IngestionFormat.PROWLER
        if "assetAttributes" in v0 or "service" in v0:
            return IngestionFormat.AWS_INSPECTOR

    # --- XML content sniffing ----------------------------------------
    if b"<NessusClientData_v2" in head or b"<NessusClientData>" in head:
        return IngestionFormat.NESSUS
    if b"<nmaprun" in head or b"<nmap>" in head:
        return IngestionFormat.NMAP
    if b"<OWASPZAPReport" in head or b"owasp_zap_report" in head.lower():
        return IngestionFormat.ZAP
    if b"<MetasploitV5" in head:
        return IngestionFormat.METASPLOIT
    if b"<get_reports_response" in head or b"<get_reports" in head:
        return IngestionFormat.OPENVAS
    if b"<WAS_SCAN_REPORT" in head:
        return IngestionFormat.QUALYS
    if b"<SCAN" in head and b"<RESULT" in head and b"QID" in head:
        return IngestionFormat.QUALYS
    if b"<issues" in head and b"<issue" in head:
        return IngestionFormat.BURP
    if b"alertitem" in head:
        return IngestionFormat.ZAP

    # --- last-resort filename hints ----------------------------------
    if "burp" in n:
        return IngestionFormat.BURP
    if "zap" in n:
        return IngestionFormat.ZAP
    if "qualys" in n:
        return IngestionFormat.QUALYS
    if "openvas" in n or "gvm" in n:
        return IngestionFormat.OPENVAS
    if "trivy" in n:
        return IngestionFormat.TRIVY
    if "snyk" in n:
        return IngestionFormat.SNYK
    if "prowler" in n:
        return IngestionFormat.PROWLER
    if "testssl" in n:
        return IngestionFormat.TESTSSL
    if "wpscan" in n or "wp_scan" in n:
        return IngestionFormat.WPSCAN
    if "nikto" in n:
        return IngestionFormat.NIKTO
    if "metasploit" in n or "msf_" in n:
        return IngestionFormat.METASPLOIT
    if "inspector" in n and "aws" in n:
        return IngestionFormat.AWS_INSPECTOR
    if "kube-bench" in n or "kube_bench" in n:
        return IngestionFormat.KUBE_BENCH
    if "nuclei" in n:
        return IngestionFormat.NUCLEI

    # --- CSV/JSONL by content for nikto/nuclei -----------------------
    if b"Nikto" in head[:200]:
        return IngestionFormat.NIKTO
    if b"OSVDB" in head[:400]:
        return IngestionFormat.NIKTO

    return IngestionFormat.UNKNOWN
