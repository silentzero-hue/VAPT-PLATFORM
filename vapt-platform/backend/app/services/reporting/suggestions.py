"""Smart suggestion engine for report editor fields.

Generates realistic impact / recommendation / action-urgency text
based on a finding's severity, CVSS score, CVE category, and Nessus plugin name.

Heuristics only — outputs are starting points for the analyst to refine,
not authoritative text. The analyst must review and adjust before approving.
"""

from __future__ import annotations

import re
from typing import TypedDict

from app.models.finding import Finding, FindingStatus
from app.models.vulnerability import Vulnerability, Severity

# ---------------------------------------------------------------------------
# Action urgency
# ---------------------------------------------------------------------------
# Aligned with the DMC template's "Action urgency – Definition chart":
#   Immediate — within 7 days
#   Urgent    — within 14 working days
#   Standard  — within 30 working days
#   Normal    — next maintenance window
#   Info      — no action required

URGENCY_LABEL: dict[str, str] = {
    "critical": "Immediate",
    "high": "Urgent",
    "medium": "Standard",
    "low": "Normal",
    "info": "Info",
}


def action_urgency_for(severity: str) -> str:
    sev = severity.lower()
    return URGENCY_LABEL.get(sev, "Standard")


# ---------------------------------------------------------------------------
# CVE-category detection
# ---------------------------------------------------------------------------
_CVE_CATEGORY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"remote code execution|\brce\b|deseriali[sz]ation", re.I), "rce"),
    (re.compile(r"sql injection|\bsqli\b", re.I), "sqli"),
    (re.compile(r"cross[- ]site scripting|\bxss\b", re.I), "xss"),
    (re.compile(r"cross[- ]site request forgery|\bcsrf\b", re.I), "csrf"),
    (re.compile(r"authentication bypass|auth(?:entication)? bypass", re.I), "auth_bypass"),
    (re.compile(r"privilege escalation|local privilege|priv(ilege)? esc", re.I), "priv_esc"),
    (re.compile(r"denial of service|\bdos\b|amplyfi", re.I), "dos"),
    (re.compile(r"information disclosure|info(?:rmation)? disclosure", re.I), "info_disc"),
    (re.compile(r"buffer overflow|heap overflow|stack overflow|memory corruption", re.I), "mem_corrupt"),
    (re.compile(r"ssrf|server[- ]side request forgery", re.I), "ssrf"),
    (re.compile(r"path traversal|directory traversal|\.\./\.\.", re.I), "path_traversal"),
    (re.compile(r"xxe|xml external", re.I), "xxe"),
    (re.compile(r"open redirect", re.I), "open_redirect"),
    (re.compile(r"csrf|xsrf", re.I), "csrf"),
    (re.compile(r"man[- ]in[- ]the[- ]middle|\bmitm\b", re.I), "mitm"),
    (re.compile(r"default(?: password| credentials| account)", re.I), "default_creds"),
    (re.compile(r"outdated|unsupported version|deprecated|end[- ]of[- ]life|eol", re.I), "unsupported"),
    (re.compile(r"missing (?:security )?header|csp|x-frame|x-content|strict-transport", re.I), "missing_header"),
    (re.compile(r"tls|ssl|certificate|cipher", re.I), "weak_crypto"),
    (re.compile(r"unauthenticated|missing authentication|no authentication", re.I), "no_auth"),
    (re.compile(r"patch|missing patch|update|advisory|rhel[- ]?\d+|RHSA-", re.I), "missing_patch"),
]


def detect_cve_category(*, cve_id: str | None, title: str) -> str:
    """Heuristically classify a CVE into a category used to pick the right template."""
    if cve_id:
        # Known dangerous CVE families that are always RCE
        if re.match(r"CVE-(2017|2018|2019|2020|2021|2022|2023|2024|2025)-\d+", cve_id, re.I):
            # We don't have a CVE database locally; rely on title text.
            pass
    haystack = (title or "") + " " + (cve_id or "")
    for pattern, category in _CVE_CATEGORY_PATTERNS:
        if pattern.search(haystack):
            return category
    return "generic"


# ---------------------------------------------------------------------------
# Per-category templates
# ---------------------------------------------------------------------------
# Each category has:
#   - impact_template: a function (severity, vuln) -> str
#   - recommendation_template: a function (severity, vuln) -> str
#   - action_urgency: per-severity label override (rare; defaults to URGENCY_LABEL)
#
# Templates are written to be applicable to a wide range of findings within
# the category. They are NOT filler — they describe the realistic worst-case
# impact and the standard remediation pattern for that class of bug.

class Suggestion(TypedDict):
    impact: str
    recommendation: str
    action_urgency: str
    category: str


def _vuln_summary(vuln: Vulnerability) -> str:
    """One-line context for the analyst reading the suggestion."""
    title = (vuln.title or "").strip()
    if not title:
        return ""
    # Truncate to keep the suggestion readable
    if len(title) > 220:
        title = title[:217] + "…"
    return title


def _generic_impact(severity: str, vuln: Vulnerability) -> str:
    title = _vuln_summary(vuln)
    if severity in ("critical", "high"):
        return (
            f"A successful exploit of {title or 'this vulnerability'} on the affected asset(s) would "
            f"compromise the confidentiality, integrity, and availability of the system. "
            f"Because the affected function is exposed to {('untrusted networks' if vuln.severity.value == 'critical' else 'the network or local users')}, "
            f"an attacker could leverage this flaw to escalate privileges, exfiltrate data, "
            f"establish persistence, or pivot to other systems in the environment. "
            f"The risk is amplified where the same underlying vulnerability affects multiple assets."
        )
    if severity == "medium":
        return (
            f"Exploitation of {title or 'this vulnerability'} would allow an attacker to compromise "
            f"specific security properties of the affected asset(s). Depending on the exposure "
            f"and the data processed, this could lead to limited data disclosure, partial denial of "
            f"service, or unauthorised modification of state."
        )
    if severity == "low":
        return (
            f"Exploitation of {title or 'this vulnerability'} requires an unusual combination of "
            f"conditions or yields a limited security benefit to the attacker. The realistic impact "
            f"is bounded to information leakage or a degraded security posture."
        )
    return (
        f"This finding is informational. There is no direct security impact; the entry is recorded "
        f"to maintain a complete inventory of the asset's exposure surface."
    )


def _generic_recommendation(severity: str, vuln: Vulnerability) -> str:
    title = _vuln_summary(vuln)
    if severity in ("critical", "high"):
        return (
            f"1. Apply the vendor-supplied patch for {title or 'this issue'} without delay. "
            f"Confirm the patch level on every affected asset.\n"
            f"2. Where a patch is not yet available, apply a compensating control "
            f"(network segmentation, WAF rule, or service disablement) and document the residual risk.\n"
            f"3. Verify remediation with a re-scan of the affected asset(s) within 7 days of patching."
        )
    if severity == "medium":
        return (
            f"1. Schedule the vendor-supplied patch for {title or 'this issue'} in the next "
            f"maintenance window.\n"
            f"2. Track remediation in the issue tracker; assign an owner and a target date.\n"
            f"3. Verify with a re-scan after patching."
        )
    if severity == "low":
        return (
            f"1. Roll the vendor-supplied patch for {title or 'this issue'} into the next routine "
            f"update cycle.\n"
            f"2. If patching is deferred, document the rationale and the compensating control."
        )
    return (
        f"No action is required. Continue to track {title or 'this finding'} for asset inventory "
        f"purposes. If the affected service is upgraded in the future, re-evaluate."
    )


# Per-category overrides
def _rce_impact(severity: str, vuln: Vulnerability) -> str:
    if severity in ("critical", "high"):
        return (
            "The affected service exposes a remote code execution (RCE) vulnerability that an "
            "unauthenticated network attacker can exploit. Successful exploitation grants the "
            "attacker the privileges of the service account, which on the affected host is "
            "typically a privileged user. From there, the attacker can read or modify any data "
            "on the host, install persistent backdoors, harvest credentials, and pivot laterally to "
            "any other system the compromised host can reach. This is the worst-case impact for "
            "an internet-exposed or internal network service."
        )
    return _generic_impact(severity, vuln)


def _rce_recommendation(severity: str, vuln: Vulnerability) -> str:
    return (
        "1. Patch the affected software to the vendor-fixed version TODAY. This is non-negotiable "
        "for any service reachable from an untrusted network.\n"
        "2. Until the patch is applied, place a WAF rule or temporarily disable the vulnerable "
        "endpoint if the business function tolerates it.\n"
        "3. After patching, search the host for indicators of compromise (unfamiliar processes, "
        "suspicious cron jobs, modified binaries, new user accounts) — assume pre-patch exploitation "
        "is possible.\n"
        "4. Force a credential rotation for any account that could log in to the affected host."
    )


def _sqli_impact(severity: str, vuln: Vulnerability) -> str:
    return (
        "The affected service is vulnerable to SQL injection. An attacker can craft inputs that "
        "are interpreted as SQL, allowing arbitrary read, modification, and deletion of any data "
        "in the affected database. Depending on the database server's configuration, this can also "
        "lead to remote command execution on the database host. PII, credentials, and "
        "application secrets are at risk of full exfiltration."
    )


def _sqli_recommendation(severity: str, vuln: Vulnerability) -> str:
    return (
        "1. Replace string concatenation with parameterised queries (prepared statements) in "
        "every code path that accepts user input.\n"
        "2. Add server-side input validation as a defence-in-depth measure, but do not rely on it.\n"
        "3. Review the application's database account: it should have only the minimum privileges "
        "needed (no DDL, no xp_cmdshell, etc.).\n"
        "4. Enable database query logging and review logs for the past 90 days for evidence of "
        "prior exploitation."
    )


def _xss_impact(severity: str, vuln: Vulnerability) -> str:
    return (
        "The affected application is vulnerable to cross-site scripting. An attacker can inject "
        "arbitrary JavaScript that executes in the browser of any user who visits the affected "
        "page. The injected script can steal session cookies, exfiltrate CSRF tokens, deface the "
        "page, or pivot to actions the victim is authorised to perform. If the application "
        "serves authenticated users with elevated privileges, stored XSS can lead to full account "
        "takeover of those users."
    )


def _xss_recommendation(severity: str, vuln: Vulnerability) -> str:
    return (
        "1. Apply context-aware output encoding (HTML, attribute, JavaScript, URL) at every "
        "point where user-controlled data is rendered.\n"
        "2. Set a strict Content-Security-Policy with no 'unsafe-inline' and no wildcard sources.\n"
        "3. Mark session cookies as HttpOnly + SameSite=Strict so they cannot be exfiltrated even "
        "if XSS occurs.\n"
        "4. Where the application uses a templating engine, switch to auto-escaping mode if it is "
        "not already."
    )


def _auth_bypass_impact(severity: str, vuln: Vulnerability) -> str:
    return (
        "The affected service contains an authentication bypass that allows an unauthenticated "
        "remote attacker to gain the privileges of an authenticated user (potentially "
        "administrator). On the affected host this means full read/write/execute access to the "
        "service's data and configuration. Combined with the prevalence of credential reuse, "
        "the compromise can spread to other internal systems."
    )


def _auth_bypass_recommendation(severity: str, vuln: Vulnerability) -> str:
    return (
        "1. Apply the vendor-supplied patch immediately.\n"
        "2. Review the service's authentication and authorisation logs for the past 90 days for "
        "anomalous successful logins from unfamiliar IPs or users.\n"
        "3. Rotate all credentials (service, database, integration tokens) that the affected "
        "service had access to.\n"
        "4. Add a WAF or IDS rule that blocks the specific bypass pattern until patching is "
        "complete."
    )


def _missing_patch_impact(severity: str, vuln: Vulnerability) -> str:
    return (
        "The affected host is missing one or more vendor security patches. The patch(es) cover "
        "flaws that, depending on the package, range from local privilege escalation to remote "
        "code execution. Patching the entire backlog is essential to remove accumulated attacker "
        "opportunity, but the most critical individual advisories should be addressed first."
    )


def _missing_patch_recommendation(severity: str, vuln: Vulnerability) -> str:
    return (
        "1. Apply the latest vendor-supplied security rollup (e.g. yum update --security, apt "
        "upgrade, dnf update --security) to the affected host.\n"
        "2. Confirm the patch level with a re-scan.\n"
        "3. Subscribe the operations team to the vendor security advisory feed so future patches "
        "are surfaced automatically.\n"
        "4. Where the package cannot be patched (e.g. pinned vendor build), document the "
        "compensating control and revisit at the next major version."
    )


def _unsupported_impact(severity: str, vuln: Vulnerability) -> str:
    return (
        "The affected service is running a software version that the vendor no longer supports. "
        "New security vulnerabilities disclosed against this version will not be patched by the "
        "vendor. Over time the system accumulates an unbounded backlog of unpatchable "
        "vulnerabilities and should be considered permanently at risk."
    )


def _unsupported_recommendation(severity: str, vuln: Vulnerability) -> str:
    return (
        "1. Plan a migration to a vendor-supported version. If the affected version is more than "
        "one major release behind, schedule the upgrade within the next 90 days.\n"
        "2. Until the migration completes, apply network-level isolation: restrict the service "
        "to trusted internal hosts only and place it behind a WAF or reverse proxy.\n"
        "3. After the upgrade, repeat the assessment to confirm the new version is not itself "
        "missing critical patches."
    )


def _weak_crypto_impact(severity: str, vuln: Vulnerability) -> str:
    return (
        "The affected service uses weak cryptographic primitives (deprecated cipher suites, "
        "short key lengths, or vulnerable protocol versions). An attacker positioned on the "
        "network path between the client and the service can passively decrypt traffic, perform "
        "man-in-the-middle attacks, or forge signatures. This is a high-impact class of bug for "
        "any service that authenticates users, exchanges sensitive data, or signs assertions."
    )


def _weak_crypto_recommendation(severity: str, vuln: Vulnerability) -> str:
    return (
        "1. Disable the vulnerable cipher suites and protocol versions. Use only TLS 1.2+ with "
        "AEAD ciphers (AES-GCM, ChaCha20-Poly1305) and SHA-256 or stronger.\n"
        "2. Configure the service to prefer ECDHE key exchange for forward secrecy.\n"
        "3. Verify with `nmap --script ssl-enum-ciphers` or `testssl.sh`.\n"
        "4. Update internal client libraries to remove the deprecated fallback paths."
    )


def _default_creds_impact(severity: str, vuln: Vulnerability) -> str:
    return (
        "The affected service is reachable with a vendor-default or well-known account. Any "
        "attacker with a copy of the vendor documentation can log in without any prior access, "
        "and from there can read or modify the service's data, change configuration, or pivot to "
        "the underlying host. This is functionally equivalent to a remote unauthenticated access "
        "flaw."
    )


def _default_creds_recommendation(severity: str, vuln: Vulnerability) -> str:
    return (
        "1. Disable the default account or rotate its password to a unique, high-entropy value.\n"
        "2. Restrict the affected management interface to a trusted network segment.\n"
        "3. Add an alert on any future login from the default account — it should never be used "
        "in production.\n"
        "4. Audit the service for other vendor-default credentials (admin/admin, root/root, etc.)."
    )


def _info_disc_impact(severity: str, vuln: Vulnerability) -> str:
    return (
        "The affected service discloses information (banner, version, configuration) that helps "
        "an attacker fingerprint the service and select known exploits. The disclosure itself is "
        "low-impact, but it materially reduces the time and cost of the next attack phase."
    )


def _info_disc_recommendation(severity: str, vuln: Vulnerability) -> str:
    return (
        "1. Suppress detailed version banners in production. Most web servers, frameworks, and "
        "application servers have a configuration switch for this.\n"
        "2. Remove sample applications, debug endpoints, and default error pages from production.\n"
        "3. Re-scan to confirm the banner is now generic."
    )


def _dos_impact(severity: str, vuln: Vulnerability) -> str:
    return (
        "The affected service can be made unavailable by a remote attacker with limited resources. "
        "Sustained exploitation results in lost revenue, failed SLAs, and (if the service is a "
        "shared dependency) cascading outages across other systems. The service can typically be "
        "recovered by restarting it, but the attacker can re-trigger the crash at will."
    )


def _dos_recommendation(severity: str, vuln: Vulnerability) -> str:
    return (
        "1. Apply the vendor-supplied patch.\n"
        "2. Place a WAF or rate-limiter in front of the service to absorb traffic spikes.\n"
        "3. Configure the service to restart automatically on crash, and set up an alert on "
        "restart rate so an ongoing attack is visible.\n"
        "4. Where the service is internet-facing, confirm with the ISP that volumetric DDoS "
        "protection is in place."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
CATEGORY_FUNCTIONS: dict[str, tuple] = {
    "rce":           (_rce_impact,           _rce_recommendation),
    "sqli":          (_sqli_impact,          _sqli_recommendation),
    "xss":           (_xss_impact,           _xss_recommendation),
    "auth_bypass":   (_auth_bypass_impact,   _auth_bypass_recommendation),
    "missing_patch": (_missing_patch_impact, _missing_patch_recommendation),
    "unsupported":   (_unsupported_impact,   _unsupported_recommendation),
    "weak_crypto":   (_weak_crypto_impact,   _weak_crypto_recommendation),
    "default_creds": (_default_creds_impact, _default_creds_recommendation),
    "info_disc":     (_info_disc_impact,     _info_disc_recommendation),
    "dos":           (_dos_impact,           _dos_recommendation),
    # Categories that fall through to the generic text:
    "csrf":          (_generic_impact,       _generic_recommendation),
    "priv_esc":      (_generic_impact,       _generic_recommendation),
    "mem_corrupt":   (_rce_impact,           _rce_recommendation),
    "ssrf":          (_generic_impact,       _generic_recommendation),
    "path_traversal":(_generic_impact,       _generic_recommendation),
    "xxe":           (_generic_impact,       _generic_recommendation),
    "open_redirect": (_generic_impact,       _generic_recommendation),
    "mitm":          (_weak_crypto_impact,   _weak_crypto_recommendation),
    "no_auth":       (_auth_bypass_impact,   _auth_bypass_recommendation),
    "missing_header":(_generic_impact,       _generic_recommendation),
    "generic":       (_generic_impact,       _generic_recommendation),
}


def suggest(vuln: Vulnerability, *, severity_override: str | None = None) -> Suggestion:
    """Return a Suggestion dict for the given vulnerability.

    `severity_override` allows the caller to use a different severity than
    the vulnerability's intrinsic one (e.g. when the analyst has marked it
    differently in the report editor).
    """
    sev = (severity_override or vuln.severity.value or "info").lower()
    category = detect_cve_category(cve_id=vuln.cve_id, title=vuln.title or "")
    impact_fn, rec_fn = CATEGORY_FUNCTIONS.get(category, CATEGORY_FUNCTIONS["generic"])
    return Suggestion(
        impact=impact_fn(sev, vuln),
        recommendation=rec_fn(sev, vuln),
        action_urgency=action_urgency_for(sev),
        category=category,
    )


def suggest_for_finding(
    finding: Finding,
    vuln: Vulnerability | None,
    *,
    severity_override: str | None = None,
) -> Suggestion:
    """Same as `suggest`, but takes a Finding + optional Vulnerability. If
    `vuln` is None, fall back to the generic template."""
    if vuln is None:
        # Use a synthetic stub so the impact / recommendation functions
        # still have something to work with.
        from app.models.vulnerability import Vulnerability as V
        from app.models.finding import FindingStatus
        # `vuln_title` lives on the API response (joined from Vulnerability),
        # not on the model. Fall back to the vulnerability_id placeholder.
        stub = V(
            id=finding.vulnerability_id,
            workspace_id=finding.workspace_id,
            title="(no title)",
            description="",
            severity=finding.effective_severity,
        )
        return suggest(stub, severity_override=severity_override)
    return suggest(vuln, severity_override=severity_override)
