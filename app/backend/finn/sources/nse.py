"""NSE adapters: security master (identity), security-wise daily reports (EOD) and
corporate announcements. The same functions serve every ticker."""
from __future__ import annotations

import csv
import io
import json
import re
from urllib.parse import urlencode
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..config import IST
from ..contracts import Company
from ..db import Store, sha256_bytes, utcnow
from .fetch import Fetcher

EQUITY_LIST_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
EOD_SCHEMA = "nse-sec_bhavdata_full-v1"
ANNOUNCEMENTS_API = "https://www.nseindia.com/api/corporate-announcements"
ANNUAL_REPORTS_API = "https://www.nseindia.com/api/annual-reports"


class IdentityError(Exception):
    def __init__(self, state: str, message: str):
        super().__init__(message)
        self.state = state  # unknown_symbol | source_unavailable


def _norm_row(row: Dict[str, Any]) -> Dict[str, str]:
    return {(k or "").strip().upper(): (v or "").strip() for k, v in row.items()}


# ---------------------------------------------------------------- identity
def parse_equity_list(data: bytes) -> List[Dict[str, str]]:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    out = []
    for raw in reader:
        row = _norm_row(raw)
        if not row.get("SYMBOL"):
            continue
        out.append(
            {
                "symbol": row["SYMBOL"].upper(),
                "legal_name": row.get("NAME OF COMPANY", ""),
                "series": row.get("SERIES", ""),
                "listing_date": row.get("DATE OF LISTING") or None,
                "isin": row.get("ISIN NUMBER", ""),
            }
        )
    return out


def refresh_security_master(store: Store, fetcher: Fetcher) -> Tuple[bool, str]:
    res = fetcher.get(EQUITY_LIST_URL, source_kind="nse_security_master", expect="csv")
    if not res.ok:
        return False, f"{res.state}: {res.error}"
    rows = parse_equity_list(res.content)
    if not rows:
        return False, "security master parsed to zero rows"
    for r in rows:
        store.insert(
            "security_master",
            {**r, "source_url": EQUITY_LIST_URL, "source_hash": res.content_hash, "retrieved_at": res.retrieved_at},
            mode="INSERT OR REPLACE",
        )
    return True, f"{len(rows)} securities"


def resolve_company(store: Store, symbol: str, fetcher: Optional[Fetcher] = None) -> Company:
    """Resolve an NSE symbol to legal name/ISIN/series from the latest stored security master.

    If the symbol is unknown and a fetcher is supplied, refresh the master once before
    rejecting it (an unknown symbol triggers a fresh lookup)."""
    symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9&\-]{1,20}", symbol):
        raise IdentityError("unknown_symbol", "symbol contains unsupported characters")
    row = _latest_master_row(store, symbol)
    if row is None and fetcher is not None:
        ok, msg = refresh_security_master(store, fetcher)
        if not ok and not _any_master(store):
            raise IdentityError("source_unavailable", f"NSE security master unavailable ({msg})")
        row = _latest_master_row(store, symbol)
    if row is None:
        if not _any_master(store):
            raise IdentityError("source_unavailable", "no NSE security master has been retrieved yet")
        raise IdentityError("unknown_symbol", f"{symbol} is not in the NSE equity security master")
    company = Company(
        company_id=f"isin:{row['isin']}",
        symbol=row["symbol"],
        legal_name=row["legal_name"],
        isin=row["isin"],
        series=row["series"],
        listing_date=row["listing_date"],
        identity_source_url=row["source_url"],
        identity_source_hash=row["source_hash"],
        resolved_at=utcnow(),
    )
    store.insert("companies", company.model_dump(), mode="INSERT OR REPLACE")
    return company


def _latest_master_row(store: Store, symbol: str) -> Optional[Dict[str, Any]]:
    return store.query_one(
        "SELECT * FROM security_master WHERE symbol=? ORDER BY retrieved_at DESC LIMIT 1", (symbol,)
    )


def _any_master(store: Store) -> bool:
    return store.query_one("SELECT 1 AS x FROM security_master LIMIT 1") is not None


# ---------------------------------------------------------------- EOD
def eod_url(day: date) -> str:
    return f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{day.strftime('%d%m%Y')}.csv"


def _num(value: str) -> Optional[float]:
    value = (value or "").replace(",", "").strip()
    if value in ("", "-"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_sec_bhavdata(data: bytes, symbols: Iterable[str], expected_day: date) -> List[Dict[str, Any]]:
    wanted = {s.upper() for s in symbols}
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    rows = []
    for raw in reader:
        row = _norm_row(raw)
        if row.get("SYMBOL", "").upper() not in wanted:
            continue
        try:
            file_day = datetime.strptime(row.get("DATE1", ""), "%d-%b-%Y").date()
        except ValueError:
            file_day = None
        qty = _num(row.get("TTL_TRD_QNTY", ""))
        rows.append(
            {
                "symbol": row["SYMBOL"].upper(),
                "series": row.get("SERIES", ""),
                "trading_date": (file_day or expected_day).isoformat(),
                "open": _num(row.get("OPEN_PRICE", "")),
                "high": _num(row.get("HIGH_PRICE", "")),
                "low": _num(row.get("LOW_PRICE", "")),
                "close": _num(row.get("CLOSE_PRICE", "")),
                "prev_close": _num(row.get("PREV_CLOSE", "")),
                "volume": int(qty) if qty is not None else None,
                "validation_status": "valid" if file_day == expected_day else "date_mismatch",
            }
        )
    return rows


def ingest_eod_day(store: Store, fetcher: Fetcher, day: date, companies: List[Company]) -> Dict[str, Any]:
    url = eod_url(day)
    res = fetcher.get(url, source_kind="nse_eod", expect="csv")
    summary = {"date": day.isoformat(), "url": url, "state": res.state, "rows": 0, "error": res.error}
    if not res.ok:
        return summary
    by_symbol = {c.symbol: c for c in companies}
    rows = parse_sec_bhavdata(res.content, by_symbol.keys(), day)
    rejected = [r for r in rows if r["validation_status"] != "valid"]
    if rejected:
        # A date-specific URL can return a different session's CSV. Preserve the
        # downloaded bytes/attempt, but never let it overwrite that session's
        # valid observation or appear as data for the requested day.
        summary.update(state="invalid_document", error="report trading date does not match requested date",
                       rejected_rows=[{"symbol": r["symbol"], "reported_date": r["trading_date"]} for r in rejected])
        store.execute("UPDATE fetch_attempts SET state='invalid_document', error=? WHERE attempt_id=?",
                      (summary["error"], res.attempt_id))
        return summary
    for r in rows:
        r["isin"] = by_symbol[r["symbol"]].isin
        r.update(source_url=url, source_hash=res.content_hash, schema_version=EOD_SCHEMA, retrieved_at=res.retrieved_at)
        store.insert("market_observations", r, mode="INSERT OR REPLACE")
    summary["rows"] = len(rows)
    return summary


# ---------------------------------------------------------------- announcements
def parse_nse_timestamp(raw: Optional[str]) -> Optional[str]:
    """Parse NSE '17-Apr-2025 16:23:14' (IST) into a UTC ISO string."""
    if not raw:
        return None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%m-%Y %H:%M:%S"):
        try:
            local = datetime.strptime(raw.strip(), fmt).replace(tzinfo=IST)
            return local.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def announcements_url(symbol: str, start: date, end: date) -> str:
    return ANNOUNCEMENTS_API + "?" + urlencode({"index": "equities", "symbol": symbol,
                                               "from_date": start.strftime('%d-%m-%Y'), "to_date": end.strftime('%d-%m-%Y')})


def fetch_announcements(fetcher: Fetcher, company: Company, start: date, end: date):
    if not fetcher._nse_session_ready:
        fetcher.ensure_nse_session()
    url = announcements_url(company.symbol, start, end)
    res = fetcher.get(
        url,
        source_kind="nse_announcements",
        expect="json",
        company_id=company.company_id,
        headers={"Accept": "application/json", "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements"},
    )
    records: List[Dict[str, Any]] = []
    if res.ok:
        payload = res.json()
        records = payload if isinstance(payload, list) else payload.get("data", []) if isinstance(payload, dict) else []
    return res, records


def store_announcements(store: Store, company: Company, res, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    stored = []
    for rec in records:
        if (rec.get("symbol") or company.symbol).upper() != company.symbol:
            continue  # never attach another company's record
        raw_time = rec.get("exchdisstime") or rec.get("an_dt") or rec.get("sort_date")
        attachment = (rec.get("attchmntFile") or "").strip() or None
        key_material = f"{company.symbol}|{rec.get('seq_id') or ''}|{raw_time}|{attachment}|{rec.get('desc')}"
        source_key = sha256_bytes(key_material.encode())[:24]
        row = {
            "announcement_id": f"ann_{source_key[:16]}",
            "company_id": company.company_id,
            "source_key": source_key,
            "category": rec.get("desc"),
            "subject": rec.get("attchmntText") or rec.get("desc"),
            "published_at": parse_nse_timestamp(raw_time),
            "published_at_raw": raw_time,
            "attachment_url": attachment,
            "attachment_version_id": None,
            "attachment_state": "not_attempted" if attachment else None,
            "retrieved_at": res.retrieved_at,
            "source_url": res.url,
            "source_hash": res.content_hash,
            "raw_json": json.dumps(rec, sort_keys=True),
        }
        existing = store.query_one("SELECT announcement_id, attachment_version_id, attachment_state FROM announcements WHERE source_key=?", (source_key,))
        if existing:
            row["attachment_version_id"] = existing["attachment_version_id"]
            row["attachment_state"] = existing["attachment_state"]
            row["announcement_id"] = existing["announcement_id"]
        store.insert("announcements", row, mode="INSERT OR REPLACE")
        stored.append(row)
    return stored


def fetch_annual_report_index(fetcher: Fetcher, company: Company):
    if not fetcher._nse_session_ready:
        fetcher.ensure_nse_session()
    url = ANNUAL_REPORTS_API + "?" + urlencode({"index": "equities", "symbol": company.symbol})
    res = fetcher.get(url, source_kind="nse_annual_report_index", expect="json", company_id=company.company_id,
                      headers={"Accept": "application/json", "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-annual-reports"})
    records: List[Dict[str, Any]] = []
    if res.ok:
        payload = res.json()
        records = payload.get("data", []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    return res, records
