"""Explicit, bounded current-announcement checks using primary NSE metadata only.

This path never retrieves PDFs, resolves an unknown company over the network, or
uses a model. Failed checks keep existing announcements and are reported separately
from companies whose source response was actually fetched and validated.
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, Iterable, List, Optional

import httpx

from .config import IST, Settings
from .db import Store
from .sources import nse
from .sources.documents import link_existing_versions
from .sources.fetch import UnsafeURL, validate_public_https

MAX_COMPANIES = 15
REFRESH_BUDGET_S = 45.0
CACHE_SECONDS = 15 * 60
_clock = time.monotonic


def _now() -> datetime:
    return datetime.now(timezone.utc)


def report_path(settings: Settings) -> Path:
    return settings.data_dir / "current_refresh.json"


def read_refresh_report(settings: Settings) -> Optional[Dict[str, Any]]:
    """Return the last attempt without changing its timestamps or implying success."""
    try:
        report = json.loads(report_path(settings).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(report, dict) or not isinstance(report.get("companies"), list):
        return None
    if not all(isinstance(row, dict) and isinstance(row.get("symbol"), str) for row in report["companies"]):
        return None
    return report


def _symbols(values: Iterable[str]) -> List[str]:
    if isinstance(values, (str, bytes)):
        raise ValueError("Supply a list of portfolio symbols.")
    output = []
    for raw in values:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Each portfolio symbol must be a non-empty string.")
        symbol = raw.strip().upper()
        if symbol not in output:
            output.append(symbol)
        if len(output) > MAX_COMPANIES:
            raise ValueError("A current check supports at most 15 portfolio holdings.")
    if not output:
        raise ValueError("Choose at least one portfolio holding to check.")
    return output


class _DeadlineResponse:
    def __init__(self, response, deadline):
        self.response = response
        self.deadline = deadline

    def __getattr__(self, name):
        return getattr(self.response, name)

    def iter_bytes(self):
        for chunk in self.response.iter_bytes():
            if _clock() >= self.deadline:
                raise httpx.ReadTimeout("Current filing check reached its time limit.")
            yield chunk


class _DeadlineClient:
    """Apply a total deadline between response chunks and short socket timeouts.

    The underlying guarded fetcher still checks hosts, redirect hops, byte limits,
    content type and provenance. Blocking network reads can overrun the deadline
    by at most the short per-read timeout, rather than its normal 30-second limit.
    """
    def __init__(self, client, deadline):
        self.client = client
        self.deadline = deadline

    def __getattr__(self, name):
        return getattr(self.client, name)

    @contextmanager
    def stream(self, *args, **kwargs):
        remaining = self.deadline - _clock()
        if remaining <= 0:
            raise httpx.ReadTimeout("Current filing check reached its time limit.")
        kwargs["timeout"] = httpx.Timeout(max(0.05, min(3.0, remaining / 8)))
        with self.client.stream(*args, **kwargs) as response:
            yield _DeadlineResponse(response, self.deadline)


class _BoundedFetcher:
    def __init__(self, fetcher, deadline):
        self.fetcher = fetcher
        self.deadline = deadline
        self.original_client = getattr(fetcher, "client", None)
        self.original_max_bytes = getattr(fetcher, "max_bytes", None)
        if self.original_client is not None:
            fetcher.client = _DeadlineClient(self.original_client, deadline)
        if self.original_max_bytes is not None:
            fetcher.max_bytes = min(self.original_max_bytes, 2 * 1024 * 1024)

    @property
    def _nse_session_ready(self):
        return self.fetcher._nse_session_ready

    def get(self, *args, **kwargs):
        if _clock() >= self.deadline:
            raise TimeoutError("Current filing check reached its time limit.")
        kwargs["retries"] = 0
        result = self.fetcher.get(*args, **kwargs)
        if _clock() >= self.deadline:
            raise TimeoutError("Current filing check reached its time limit.")
        return result

    def ensure_nse_session(self):
        result = self.get("https://www.nseindia.com/", source_kind="nse_session", expect="html", store_body=False)
        self.fetcher._nse_session_ready = result.ok
        return result

    def close(self):
        if self.original_client is not None:
            self.fetcher.client = self.original_client
        if self.original_max_bytes is not None:
            self.fetcher.max_bytes = self.original_max_bytes
        self.fetcher.close()


def _validated_records(payload: Any, symbol: str, start, end, now) -> tuple[List[Dict], int]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
        records = payload["data"]
    else:
        raise ValueError("The exchange did not return an announcement list.")
    valid, rejected = [], 0
    for record in records:
        if not isinstance(record, dict):
            rejected += 1
            continue
        raw_symbol = record.get("symbol")
        raw_time = record.get("exchdisstime") or record.get("an_dt") or record.get("sort_date")
        if not isinstance(raw_symbol, str) or raw_symbol.upper() != symbol or not isinstance(raw_time, str):
            rejected += 1
            continue
        parsed = nse.parse_nse_timestamp(raw_time)
        if not parsed:
            rejected += 1
            continue
        published = datetime.fromisoformat(parsed)
        if not start <= published.astimezone(IST).date() <= end or published > now:
            rejected += 1
            continue
        fields = [record.get(field) for field in ("desc", "attchmntText", "attchmntFile")]
        if any(value is not None and not isinstance(value, str) for value in fields):
            rejected += 1
            continue
        attachment = record.get("attchmntFile")
        if attachment:
            try:
                validate_public_https(attachment.strip())
            except UnsafeURL:
                rejected += 1
                continue
        valid.append(record)
    return valid, rejected


def _persist(settings: Settings, report: Dict[str, Any]) -> None:
    destination = report_path(settings)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".current-refresh-", suffix=".json",
                                dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def refresh_portfolio_sources(store: Store, settings: Settings, symbols: Iterable[str], fetcher_factory,
                              days: int = 7) -> Dict[str, Any]:
    """Check known portfolio companies' recent filing metadata on explicit request.

    ``checked`` counts only ``state='fetched'`` source responses. A response with
    rejected rows is ``error`` even when its valid rows were safely retained; it
    must not imply an all-clear. All old stored records survive failed checks.
    """
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 30:
        raise ValueError("Choose a current filing period of 1 to 30 days.")
    chosen = _symbols(symbols)
    now = _now()
    end = now.astimezone(IST).date()
    cached = read_refresh_report(settings)
    cached_symbols = cached.get("symbols") if cached else None
    if (cached and cached.get("days") == days and isinstance(cached_symbols, list)
            and all(isinstance(symbol, str) for symbol in cached_symbols)
            and sorted(cached_symbols) == sorted(chosen) and cached.get("to_day") == end.isoformat()):
        try:
            finished = datetime.fromisoformat(cached["finished_at"])
            age = (now - finished).total_seconds()
        except (KeyError, TypeError, ValueError):
            age = CACHE_SECONDS
        if 0 <= age < CACHE_SECONDS:
            return {**cached, "cached": True}

    start = end - timedelta(days=days - 1)
    deadline = _clock() + REFRESH_BUDGET_S
    report = {"state": "unavailable", "started_at": now.isoformat(timespec="seconds"),
              "finished_at": None, "days": days, "from_day": start.isoformat(), "to_day": end.isoformat(),
              "symbols": chosen, "checked": 0, "companies": [], "cached": False,
              "note": "Exchange announcement metadata only; no PDFs were downloaded or analysed. "
                      "Failed checks retain stored filings and do not establish that nothing happened."}
    fetcher = None
    for symbol in chosen:
        entry = {"symbol": symbol, "state": "not_checked", "announcements": 0}
        report["companies"].append(entry)
        if _clock() >= deadline:
            entry.update(state="timeout", error="The check's 45-second time limit was reached.")
            continue
        try:
            # No fetcher: unknown symbols do not trigger a security-master request.
            company = nse.resolve_company(store, symbol)
            if fetcher is None:
                fetcher = _BoundedFetcher(fetcher_factory(), deadline)
            result, _ = nse.fetch_announcements(fetcher, company, start, end)
            if not result.ok:
                entry.update(state="timeout" if result.state == "timeout" else "error",
                             error=f"NSE could not be checked: {result.state}.")
                continue
            records, rejected = _validated_records(result.json(), symbol, start, end, _now())
            stored = nse.store_announcements(store, company, result, records)
            link_existing_versions(store, company)
            entry.update(announcements=len(stored))
            if rejected:
                entry.update(state="error", error=f"{rejected} source record(s) failed company, date or format checks.")
            else:
                entry.update(state="fetched", checked_at=_now().isoformat(timespec="seconds"))
                report["checked"] += 1
        except TimeoutError:
            entry.update(state="timeout", error="The check's 45-second time limit was reached.")
        except nse.IdentityError as exc:
            entry.update(state="not_checked", error=f"Company identity could not be verified: {exc.state}.")
        except Exception as exc:  # source/parse failure cannot erase another company's successful check
            entry.update(state="error", error=f"The source check failed ({exc.__class__.__name__}).")
    if fetcher is not None:
        fetcher.close()
    report["finished_at"] = _now().isoformat(timespec="seconds")
    if report["checked"] == len(chosen):
        report["state"] = "completed"
    elif report["checked"]:
        report["state"] = "partial"
    _persist(settings, report)
    return report
