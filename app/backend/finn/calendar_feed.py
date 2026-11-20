"""Build an all-day calendar from verified date fields in NSE public feeds."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from .config import IST
from .sources.xbrl import _allowed_exchange_file, _parse_date

_BASE = "https://www.nseindia.com"
FEEDS = (
    ("results", "/api/event-calendar", "symbol", "date", "purpose", "bm_desc"),
    ("board", "/api/corporate-board-meetings", "bm_symbol", "bm_date", "bm_purpose", "bm_desc"),
    ("record", "/api/corporates-corporateActions", "symbol", "recDate", "subject", "subject"),
)


def select_events(feeds, symbols, today: date):
    permitted = set(symbols)
    events = {}
    for (kind, path, symbol_field, date_field, purpose_field, text_field), rows in feeds:
        if not isinstance(rows, list):
            raise ValueError(f"NSE {kind} calendar response did not contain an event list")
        for row in rows:
            if not isinstance(row, dict) or row.get(symbol_field) not in permitted:
                continue
            symbol = row[symbol_field]
            day = _parse_date(row.get(date_field))
            if not day or not today <= date.fromisoformat(day) <= today + timedelta(days=120):
                continue
            purpose = str(row.get(purpose_field) or "").strip()
            description = str(row.get(text_field) or purpose).strip()
            if kind == "results" and "result" not in purpose.lower():
                continue
            label = {"results": "Financial results", "board": "Board meeting", "record": "Record date"}[kind]
            if kind == "board" and "result" in (purpose + " " + description).lower():
                label = "Financial results"
            key = (symbol, day, label, purpose if kind == "record" else "")
            attachment = _allowed_exchange_file(row.get("attachment"), (".pdf", ".xml", ".html", ".xhtml"))
            event = {"symbol": symbol, "date": day, "label": label, "description": description,
                     "source": attachment or _BASE + path + "?index=equities"}
            if key not in events or attachment:
                events[key] = event
    return sorted(events.items(), key=lambda pair: (pair[1]["date"], pair[0]))


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def _fold(line: str) -> str:
    parts, current, size = [], "", 0
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > 75:
            parts.append(current)
            current, size = " ", 1
        current += char
        size += width
    return "\r\n".join([*parts, current])


def render_calendar(events, now: datetime) -> bytes:
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FINN//NSE Portfolio Calendar//EN",
             "X-WR-CALNAME:FINN portfolio events", f"LAST-MODIFIED:{stamp}"]
    for key, event in events:
        uid = hashlib.sha256("|".join(key).encode()).hexdigest()[:24]
        start = date.fromisoformat(event["date"])
        end = start + timedelta(days=1)
        lines.extend(["BEGIN:VEVENT", f"UID:{uid}@finn", f"DTSTAMP:{stamp}",
                      f"DTSTART;VALUE=DATE:{start:%Y%m%d}", f"DTEND;VALUE=DATE:{end:%Y%m%d}",
                      "SUMMARY:" + _escape(event["symbol"] + " · " + event["label"]),
                      "DESCRIPTION:" + _escape(event["description"]), "URL:" + event["source"],
                      "END:VEVENT"])
    lines.append("END:VCALENDAR")
    return ("\r\n".join(map(_fold, lines)) + "\r\n").encode("utf-8")


def refresh_calendar(fetcher, symbols, destination: Path, now: datetime):
    """Replace an old file only when all three NSE feeds returned usable data."""
    feeds = []
    query = urlencode({"index": "equities"})
    for feed in FEEDS:
        kind, path, *_ = feed
        result = fetcher.get(_BASE + path + "?" + query, source_kind=f"nse_calendar_{kind}",
                             expect="json", store_body=False, retries=0,
                             headers={"Accept": "application/json"})
        if not result.ok:
            raise ValueError(f"NSE {kind} calendar feed unavailable ({result.state})")
        feeds.append((feed, result.json()))
    events = select_events(feeds, symbols, now.astimezone(IST).date())
    destination.write_bytes(render_calendar(events, now))
    return len(events)
