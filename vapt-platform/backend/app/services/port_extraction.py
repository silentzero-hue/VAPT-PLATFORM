"""Port extraction & normalization.

The legacy tool had `test_port_extraction.py` — meaning it explicitly
handled a mess of port representations in scan output:

  - "443/tcp"        → (443, "tcp")
  - "443"            → (443, "tcp")
  - "general/tcp"    → (0,   "tcp")  # represents "all ports"
  - "tcp/0"          → (0,   "tcp")
  - "N/A"            → (None, None)
  - ""               → (None, None)
  - "443-445"        → (443, "tcp")  # we record the low port; range is rare
  - "https"          → (443, "tcp")  # service name → IANA port
  - "ssh"            → (22,  "tcp")
  - "domain"         → (53,  "tcp")  # DNS

Service-to-port table is the IANA "well-known" subset, with the
common security-tool aliases merged in (e.g. ws-discovery → 3702).
"""

from __future__ import annotations

import re

SERVICE_TO_PORT: dict[str, tuple[int, str]] = {
    # service_name (lowercased) -> (port, protocol)
    "ftp": (21, "tcp"), "ssh": (22, "tcp"), "telnet": (23, "tcp"),
    "smtp": (25, "tcp"), "dns": (53, "tcp"), "domain": (53, "tcp"),
    "http": (80, "tcp"), "pop3": (110, "tcp"), "rpc": (111, "tcp"),
    "imap": (143, "tcp"), "snmp": (161, "udp"), "ldap": (389, "tcp"),
    "https": (443, "tcp"), "smtps": (465, "tcp"), "syslog": (514, "udp"),
    "ldaps": (636, "tcp"), "rsync": (873, "tcp"), "imaps": (993, "tcp"),
    "pop3s": (995, "tcp"), "mssql": (1433, "tcp"), "oracle": (1521, "tcp"),
    "nfs": (2049, "tcp"), "mysql": (3306, "tcp"), "rdp": (3389, "tcp"),
    "postgres": (5432, "tcp"), "vnc": (5900, "tcp"), "couchdb": (5984, "tcp"),
    "redis": (6379, "tcp"), "http-alt": (8080, "tcp"), "https-alt": (8443, "tcp"),
    "elasticsearch": (9200, "tcp"), "kibana": (5601, "tcp"),
    "docker": (2375, "tcp"), "docker-tls": (2376, "tcp"),
    "etcd": (2379, "tcp"), "kubernetes": (6443, "tcp"),
    "mqtt": (1883, "tcp"), "amqp": (5672, "tcp"),
    "memcached": (11211, "tcp"), "mongodb": (27017, "tcp"),
    "neo4j": (7687, "tcp"), "kafka": (9092, "tcp"),
    "winrm": (5985, "tcp"), "winrm-https": (5986, "tcp"),
}


_RANGE_RE = re.compile(r"^(\d+)\s*-\s*(\d+)(?:/(\w+))?$")
_PORT_PROTO_RE = re.compile(r"^(\d+)(?:/(\w+))?$")
_PROTO_PORT_RE = re.compile(r"^(\w+)/(\d+)$")


def extract_port(raw: str | int | None) -> tuple[int | None, str | None]:
    """Normalize a scan output's port representation."""
    if raw is None:
        return None, None
    if isinstance(raw, int):
        return (raw if raw > 0 else None, "tcp")
    s = str(raw).strip().lower()
    if not s or s in ("n/a", "none", "general", "general/tcp"):
        if s.startswith("general"):
            return 0, "tcp"
        return None, None
    if s in SERVICE_TO_PORT:
        return SERVICE_TO_PORT[s]
    m = _RANGE_RE.match(s)
    if m:
        return int(m.group(1)), m.group(3) or "tcp"
    m = _PORT_PROTO_RE.match(s)
    if m:
        p = int(m.group(1))
        return (p if p > 0 else None), m.group(2) or "tcp"
    m = _PROTO_PORT_RE.match(s)
    if m:
        p = int(m.group(2))
        return (p if p > 0 else None), m.group(1)
    return None, None


def canonical_port_string(port: int | None, protocol: str | None) -> str:
    if port is None:
        return ""
    proto = protocol or "tcp"
    return f"{port}/{proto}"
