"""Deterministic, opt-in phone alerts with local dry-run support.

Only leading-tier exchange announcements, explicitly selected categories, and
the existing raw EOD anomaly flags can become messages. This module never calls
an AI model and never describes a price move as caused by a filing.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urlparse

import httpx

from .config import IST
from .sources.fetch import NSE_HOSTS

DEFAULT_SITE_URL = "https://arathii23.github.io/finn-enam"
ADVICE_FOOTER = "For information only. Not investment advice."
MAX_ALERTS_KEPT = 5000
ALERT_STATE_SCHEMA = 1

_CATEGORY_LABELS = {
    "results": "Results", "M&A": "M&A", "management_change": "Management",
    "fund_raise": "Capital raising", "litigation": "Regulatory / legal",
    "credit_rating": "Credit rating", "dividend": "Dividend", "capex": "Capex",
    "earnings_call": "Earnings call", "investor_meetings": "Investor meeting",
    "press_release": "Company update", "agm_egm": "Shareholder meeting",
    "pledging": "Promoter pledge", "bonus_split": "Bonus / split",
    "insider_trading": "Insider disclosure", "unclassified": "Company filing",
}


def empty_state() -> Dict[str, Any]:
    return {"schema": ALERT_STATE_SCHEMA, "sent": {}}


def load_state(path: Path) -> Dict[str, Any]:
    """Load dedupe state. A corrupt file is an error; silently resetting could resend alerts."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return empty_state()
    except (OSError, ValueError) as exc:
        raise ValueError(f"Alert state could not be read: {exc.__class__.__name__}") from exc
    if (not isinstance(value, dict) or value.get("schema") != ALERT_STATE_SCHEMA
            or not isinstance(value.get("sent"), dict)):
        raise ValueError("Alert state has an unsupported shape; refusing to clear deduplication history.")
    return {"schema": ALERT_STATE_SCHEMA, "sent": value["sent"]}


def save_state(path: Path, state: Dict[str, Any]) -> None:
    """Atomically write dedupe state after sends have succeeded."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".alerts-", suffix=".json",
                                dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _is_nse_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in NSE_HOSTS and not parsed.username and not parsed.password


def _company_url(site_url: str, symbol: str) -> str:
    return f"{site_url.rstrip('/')}/#/c/{quote(symbol, safe='')}?mode=live"


def _published(value: Optional[str]) -> str:
    if not value:
        return "Publication time not supplied by the source."
    try:
        stamp = datetime.fromisoformat(value).astimezone(timezone.utc)
        return "Published " + stamp.strftime("%d %b %Y %H:%M UTC") + "."
    except (TypeError, ValueError):
        return "Publication time not supplied by the source."


def build_notifications(portfolio: Dict[str, Any], price_snapshot: Dict[str, Any], *,
                        checked_symbols: Optional[Iterable[str]] = None,
                        extra_categories: Iterable[str] = (),
                        site_url: str = DEFAULT_SITE_URL,
                        now: Optional[datetime] = None, days: int = 7) -> List[Dict[str, Any]]:
    """Build safe message candidates from FINN's existing Review and EOD read models."""
    checked = {str(s).upper() for s in checked_symbols} if checked_symbols is not None else None
    extras = {str(c).strip().lower() for c in extra_categories if str(c).strip()}
    allowed_symbols = {company.get("symbol") for company in portfolio.get("companies", []) if isinstance(company, dict)}
    out: List[Dict[str, Any]] = []
    for company in portfolio.get("companies", []):
        if not isinstance(company, dict):
            continue
        symbol = str(company.get("symbol") or "").strip().upper()
        if not symbol or (checked is not None and symbol not in checked):
            continue
        events = list(company.get("leading_events") or [])
        events.extend(event for event in (company.get("notable_events") or [])
                      if str(event.get("ref_category") or "").lower() in extras)
        seen_ids = set()
        for event in events:
            if not isinstance(event, dict):
                continue
            if now is not None:
                try:
                    published = datetime.fromisoformat(event.get("published_at") or "")
                    age = (now.astimezone(IST).date() - published.astimezone(IST).date()).days
                    if published.tzinfo is None or published > now or not 0 <= age < days:
                        continue
                except ValueError:
                    continue
            event_id = str(event.get("announcement_id") or "").strip()
            if not event_id or event_id in seen_ids:
                continue
            seen_ids.add(event_id)
            category = str(event.get("ref_category") or "unclassified")
            label = _CATEGORY_LABELS.get(category, "Company filing")
            subject = re.sub(r"\s+", " ", str(event.get("subject") or event.get("category") or label)).strip()
            subject = subject[:240] + ("…" if len(subject) > 240 else "")
            filing_url = event.get("attachment_url")
            if not _is_nse_url(filing_url):
                filing_url = event.get("source_url") if _is_nse_url(event.get("source_url")) else None
            links = [f"Company: {_company_url(site_url, symbol)}"]
            if filing_url:
                links.append(f"Exchange filing: {filing_url}")
            elif event.get("attachment_url"):
                links.append("Exchange filing link was not an approved NSE URL.")
            body = "\n".join([subject, _published(event.get("published_at")), *links, ADVICE_FOOTER])
            out.append({"key": f"filing:{event_id}", "kind": "filing", "symbol": symbol,
                        "category": category, "title": f"{symbol} · {label}", "body": body,
                        "published_at": event.get("published_at"), "filing_url": filing_url,
                        "company_url": _company_url(site_url, symbol)})

    for company in price_snapshot.get("companies", []):
        if not isinstance(company, dict) or company.get("state") != "ok":
            continue
        anomaly = company.get("anomaly") or {}
        latest = company.get("latest") or {}
        symbol = str(company.get("symbol") or "").strip().upper()
        trading_date = str(anomaly.get("trading_date") or latest.get("trading_date") or "")
        flags = anomaly.get("flags") or []
        if not symbol or not trading_date or not anomaly.get("flagged") or not flags:
            continue
        if now is not None:
            if symbol not in allowed_symbols:
                continue
            try:
                session = date.fromisoformat(trading_date)
                local = now.astimezone(IST)
                if not 0 <= (local.date() - session).days <= 5:
                    continue
                if session == local.date() and (local.hour, local.minute) < (15, 30):
                    continue
            except ValueError:
                continue
        key = f"eod:{symbol}:{trading_date}"
        values = "; ".join(str(flag) for flag in flags[:3])
        close = latest.get("close")
        body = "\n".join([
            f"Raw, unadjusted EOD flag for {trading_date}: {values}.",
            f"Latest close: {close} {company.get('currency') or ''}.".strip() if close is not None else "Latest close not supplied.",
            f"Company: {_company_url(site_url, symbol)}",
            "This move is not attributed to any filing.", ADVICE_FOOTER,
        ])
        out.append({"key": key, "kind": "eod", "symbol": symbol, "category": "eod_anomaly",
                    "title": f"{symbol} · EOD move", "body": body,
                    "published_at": trading_date, "filing_url": None, "company_url": _company_url(site_url, symbol)})
    return out


def pending_notifications(candidates: List[Dict[str, Any]], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    seen = set(state.get("sent", {}))
    pending = []
    for candidate in candidates:
        if candidate["key"] not in seen:
            pending.append(candidate)
            seen.add(candidate["key"])
    return pending


def send_pending(candidates: List[Dict[str, Any]], state: Dict[str, Any], *, topic: str,
                 sender: Optional[Callable[[str, Dict[str, Any]], None]] = None,
                 now: Optional[datetime] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Deliver each candidate and return updated state plus an outcome report.

    State is only updated for accepted messages. The caller persists it atomically.
    """
    topic = topic.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", topic):
        raise ValueError("Set NTFY_TOPIC to a 1–64 character public topic name using letters, numbers, _ or -.")
    deliver = sender or _send_ntfy
    sent = dict(state.get("sent", {}))
    outcomes = {"sent": [], "failed": [], "filing_delay_seconds": []}
    for item in pending_notifications(candidates, state):
        try:
            deliver(topic, item)
        except Exception as exc:  # continue: one bad delivery should not suppress other alerts
            outcomes["failed"].append({"key": item["key"], "error": exc.__class__.__name__})
            continue
        timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        sent[item["key"]] = {"sent_at": timestamp.isoformat(timespec="seconds")}
        if item["kind"] == "filing":
            try:
                published = datetime.fromisoformat(item.get("published_at") or "")
                if published.tzinfo is not None and published <= timestamp:
                    outcomes["filing_delay_seconds"].append(int((timestamp - published).total_seconds()))
            except ValueError:
                pass
        outcomes["sent"].append(item["key"])
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=90)
    trimmed = {}
    for key, value in sent.items():
        try:
            stamp = datetime.fromisoformat(value["sent_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if stamp.tzinfo is not None and stamp >= cutoff:
            trimmed[key] = value
    if len(trimmed) > MAX_ALERTS_KEPT:
        trimmed = dict(sorted(trimmed.items(), key=lambda pair: pair[1]["sent_at"])[-MAX_ALERTS_KEPT:])
    return {"schema": ALERT_STATE_SCHEMA, "sent": trimmed}, outcomes


def _send_ntfy(topic: str, item: Dict[str, Any]) -> None:
    response = httpx.post("https://ntfy.sh", json={"topic": topic, "title": item["title"], "message": item["body"],
                                                    "click": item["company_url"]},
                          timeout=15.0, follow_redirects=False)
    response.raise_for_status()


def categories_from_env(value: Optional[str] = None) -> List[str]:
    raw = os.environ.get("FINN_ALERT_CATEGORIES", "") if value is None else value
    return [part.strip().lower() for part in raw.split(",") if part.strip()]
