"""Metadata-only portfolio digest selected by the extraction spike gate.

A digest never fetches attachments, changes their priority based on extracted text,
or calls a model. The existing bounded current check owns exchange validation.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from .sources.fetch import NSE_HOSTS

MAX_BYTES = 2_000_000
MAX_ITEMS = 2000
KEEP_DAYS = 14
DAY_SECONDS = 86400
PREVIOUS_URL = "https://raw.githubusercontent.com/arathii23/finn-enam/live-data/digest.json"


def stamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except ValueError:
        return None


def exchange_url(value):
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        if url.scheme == "https" and url.hostname in NSE_HOSTS and not url.username and not url.password and url.port in (443, None):
            return value
    except ValueError:
        pass
    return None


def validate_digest(payload, now=None):
    """Reject malformed or future records before serving, merging or publishing."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise ValueError("Unsupported digest schema.")
    generated = stamp(payload.get("generated_at"))
    if not generated or generated > now + timedelta(minutes=1):
        raise ValueError("Invalid digest generation timestamp.")
    checks, items, window = payload.get("checks"), payload.get("items"), payload.get("window")
    if not isinstance(checks, dict) or not isinstance(items, list) or len(items) > MAX_ITEMS or not isinstance(window, dict):
        raise ValueError("Invalid digest data.")
    rows = checks.get("holdings")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 15 or checks.get("holdings_total") != len(rows):
        raise ValueError("Invalid digest coverage.")
    symbols = set()
    allowed_states = {"fetched", "timeout", "error", "not_checked"}
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("symbol"), str) or row["symbol"] in symbols
                or not isinstance(row.get("state"), str) or row["state"] not in allowed_states):
            raise ValueError("Invalid holding check.")
        checked_at = stamp(row.get("checked_at"))
        if (row["state"] == "fetched" and (not checked_at or checked_at > generated)
                or row["state"] != "fetched" and row.get("checked_at") is not None):
            raise ValueError("Invalid holding check time.")
        symbols.add(row["symbol"])
    checked = sum(row["state"] == "fetched" for row in rows)
    finished = stamp(checks.get("finished_at"))
    if checks.get("holdings_checked") != checked or (checked and not finished) or (finished and finished > generated):
        raise ValueError("Digest coverage and check time do not agree.")
    ids = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("symbol"), str) or item["symbol"] not in symbols:
            raise ValueError("Invalid digest item.")
        published = stamp(item.get("published_at"))
        if not published or published > generated or not isinstance(item.get("id"), str) or item["id"] in ids:
            raise ValueError("Invalid or duplicate filing identity.")
        ids.add(item["id"])
        if (item.get("tier") not in (1, 2, 3) or item.get("base_tier") != item["tier"]
                or item.get("facts") != [] or not isinstance(item.get("extraction"), dict)
                or item["extraction"].get("state") != "skipped" or item.get("headline") != item.get("subject")
                or not isinstance(item.get("version"), str) or not re.fullmatch(r"[0-9a-f]{16}", item["version"])
                or any(not isinstance(item.get(key), str) for key in ("subject", "category", "tier_reason"))):
            raise ValueError("Invalid subject-line fallback item.")
        source = item.get("source")
        if source is not None and (not isinstance(source, dict) or not exchange_url(source.get("url"))):
            raise ValueError("Invalid exchange link.")
    return payload


def read_digest(path: Path, now=None):
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Digest exceeds the size limit.")
    return validate_digest(json.loads(raw), now)


def read_previous(value: str):
    if "://" not in value:
        return read_digest(Path(value))
    if value != PREVIOUS_URL:
        raise ValueError("Only the configured public live-data digest URL is accepted.")
    import httpx
    with httpx.stream("GET", value, timeout=10, follow_redirects=False) as response:
        if response.status_code == 404:
            return None
        response.raise_for_status()
        raw = bytearray()
        for chunk in response.iter_bytes():
            raw.extend(chunk)
            if len(raw) > MAX_BYTES:
                raise ValueError("Digest exceeds the size limit.")
    return validate_digest(json.loads(raw))


def merge_previous(items, previous, generated, symbols):
    """Keep previously published filings through partial checks and feed gaps."""
    earliest = generated - timedelta(days=KEEP_DAYS)
    merged = {item["id"]: item for item in (previous or {}).get("items", [])
              if item["symbol"] in symbols and earliest <= stamp(item["published_at"]) <= generated}
    for item in items:
        old = merged.get(item["id"])
        if old and old["version"] != item["version"]:
            item = {**item, "updated": True, "prior_published_at": old["published_at"]}
        elif old and old.get("updated"):
            item = {**item, "updated": True, "prior_published_at": old.get("prior_published_at")}
        merged[item["id"]] = item
    return sorted(merged.values(), key=lambda item: (stamp(item["published_at"]), item["id"]), reverse=True)[:MAX_ITEMS]


def build_digest(queue, *, previous=None, now=None):
    now = now or datetime.now(timezone.utc)
    report = queue.get("refresh") or {}
    holdings, items = [], []
    for company in queue["companies"]:
        info = company.get("freshness") or {}
        symbol = company["symbol"]
        holdings.append({"symbol": symbol, "state": info.get("state", "not_checked"),
                         "checked_at": info.get("last_checked"), "error": info.get("error"),
                         "announcements": info.get("announcements")})
        for event in (item for key in ("leading_events", "notable_events", "routine_events")
                      for item in company.get(key, [])):
            published = stamp(event["published_at"])
            if not published or not now - timedelta(days=KEEP_DAYS) <= published <= now:
                continue
            url = exchange_url(event.get("attachment_url"))
            subject = event.get("subject") or event.get("category") or "Exchange announcement"
            version = hashlib.sha256(json.dumps([url, subject, event["published_at"]]).encode()).hexdigest()[:16]
            items.append({"id": event["announcement_id"], "version": version, "symbol": symbol,
                          "published_at": event["published_at"], "category": event["ref_category"],
                          "base_tier": event["tier"], "tier": event["tier"], "tier_reason": event["reason"],
                          "subject": subject, "headline": subject, "source": {"url": url} if url else None,
                          "facts": [], "extraction": {"state": "skipped", "reason": "Exchange subject only"}})
    holdings.sort(key=lambda row: row["symbol"])
    return validate_digest({
        "schema": 1, "generated_at": now.isoformat(),
        "checks": {"finished_at": report.get("finished_at"), "holdings_total": len(holdings),
                   "holdings_checked": sum(row["state"] == "fetched" for row in holdings),
                   "last_full_check_at": queue["summary"].get("last_full_check_at"), "holdings": holdings},
        "window": {"from": queue["window"]["filing_from"], "to": queue["window"]["filing_to"], "days": 7},
        "items": merge_previous(items, previous, now, {row["symbol"] for row in holdings}),
    }, now)


def write_atomic(path, digest):
    validate_digest(digest)
    raw = (json.dumps(digest, ensure_ascii=False, indent=2) + "\n").encode()
    if len(raw) > MAX_BYTES:
        raise ValueError("Digest exceeds the size limit.")
    tmp = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix=".finn-digest-", delete=False) as stream:
            tmp = Path(stream.name)
            stream.write(raw)
        tmp.replace(path)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)
