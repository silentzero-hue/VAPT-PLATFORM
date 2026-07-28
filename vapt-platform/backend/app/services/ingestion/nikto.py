"""Nikto CSV (default) and JSON parser.

Nikto's stock text output is plain lines; the CSV format (v2.5+) is
`"ip","port","hostname","method","uri","http_code","osvdb_id","message"`.
The newer JSON output wraps each finding in a row.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Iterable

from app.services.ingestion.nessus import NormalizedItem


_OSVDB_RE = re.compile(r"OSVDB-?(\d+)", re.IGNORECASE)
_HOST_RE = re.compile(r"//([^/:]+)")


def _parse_csv(text: str) -> Iterable[dict]:
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if not row or all(not c.strip() for c in row):
            continue
        # header row
        if len(row) >= 8 and row[0].lower() == "ip" and row[6].lower() == "osvdb_id":
            continue
        if len(row) < 8:
            continue
        yield {
            "ip": row[0],
            "port": row[1],
            "hostname": row[2],
            "method": row[3],
            "uri": row[4],
            "http_code": row[5],
            "osvdb_id": row[6],
            "message": row[7],
        }


def _parse_json(data: Any) -> Iterable[dict]:
    if isinstance(data, list):
        for v in data:
            if isinstance(v, dict):
                yield v
    elif isinstance(data, dict):
        for v in data.get("vulnerabilities", []) or []:
            if isinstance(v, dict):
                yield v


def _item_from_row(target_host: str, port: int | None, uri: str, osvdb: str, msg: str) -> NormalizedItem:
    title = msg[:400] if msg else f"OSVDB-{osvdb}" if osvdb else "Nikto finding"
    if not title and osvdb:
        title = f"OSVDB-{osvdb}"
    return NormalizedItem(
        asset_value=target_host or "unknown",
        asset_type="ip" if _looks_like_ip(target_host) else "host",
        port=port,
        protocol="tcp" if port else None,
        title=title,
        description=msg or title,
        severity="info",  # nikto doesn't carry severity
        plugin="nikto",
        plugin_id=f"osvdb-{osvdb}" if osvdb else None,
        evidence=uri,
        extra={"osvdb_id": osvdb, "uri": uri},
    )


def parse(blob: bytes) -> list[NormalizedItem]:
    text = blob.decode("utf-8", errors="replace")
    items: list[NormalizedItem] = []
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if data is not None:
            for row in _parse_json(data):
                host = row.get("ip") or row.get("hostname") or row.get("host") or "unknown"
                try:
                    port = int(row.get("port", 0)) or None
                except (TypeError, ValueError):
                    port = None
                msg = row.get("message") or row.get("description") or row.get("msg") or ""
                osvdb = str(row.get("osvdb_id") or row.get("OSVDB") or "")
                uri = row.get("uri") or row.get("url") or ""
                items.append(_item_from_row(host, port, uri, osvdb, msg))
            return items
    # CSV
    for row in _parse_csv(text):
        try:
            port = int(row.get("port", 0)) or None
        except (TypeError, ValueError):
            port = None
        host = row.get("ip") or row.get("hostname") or "unknown"
        items.append(_item_from_row(host, port, row.get("uri", ""), row.get("osvdb_id", ""), row.get("message", "")))
    return items


def _looks_like_ip(s: str) -> bool:
    parts = s.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def detect(filename: str, head: bytes) -> bool:
    n = filename.lower()
    if "nikto" in n:
        return True
    if n.endswith(".csv"):
        head_str = head.decode("utf-8", errors="replace").lower()
        if "osvdb" in head_str:
            return True
    if n.endswith(".json"):
        try:
            data = json.loads(head if head else b"")
        except Exception:
            return False
        if isinstance(data, dict) and "nikto" in str(data).lower()[:200]:
            return True
    return False
