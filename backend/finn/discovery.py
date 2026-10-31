"""Bounded, ticker-independent discovery from dated NSE source records.

No per-company URL map or model call. The exact attachment record proves when a
document was public; document headers/body prove identity and type. All HTTP
attempts and raw responses are recorded by the existing guarded fetcher.
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from .config import IST, Settings
from .contracts import Company
from .db import Store, utcnow
from .replay import classify_versions
from .sources import documents, nse
from .sources.fetch import Fetcher

DISCOVERY_VERSION = "nse-discovery-v1"
EXCHANGE_HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com", "www.nseindia.com", "nseindia.com"}


def _attachment(url: Any) -> Optional[str]:
    if not isinstance(url, str):
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme == "https" and parsed.hostname in EXCHANGE_HOSTS:
        return url.strip()
    return None


def _proof(res, record: Dict, method: str, note: str) -> List[Dict]:
    return [{"method": method, "source_url": res.url, "source_hash": res.content_hash,
             "matched_record": record, "note": note}]


def annual_candidate(record: Dict, res, company: Company) -> Optional[Dict]:
    if record.get("symbol") and record["symbol"].upper() != company.symbol:
        return None
    record_name = record.get("companyName")
    if isinstance(record_name, str) and record_name.strip():
        def name_key(name):
            base = re.sub(r"\b(?:limited|ltd\.?)\b", "", name, flags=re.I)
            return re.sub(r"[^a-z0-9]", "", base.lower())
        if name_key(record_name) != name_key(company.legal_name):
            return None
    url = _attachment(record.get("fileName") or record.get("attchmntFile"))
    if not url:
        return None
    stamp, precision, field = documents.index_publication(record)
    spec: Dict[str, Any] = {"url": url, "doc_type": "annual_report", "_discovered": True}
    # These years are the exchange index's fiscal label. Exact start/end
    # dates are deliberately not guessed from an assumed March year-end.
    try:
        first, last = int(record.get("fromYr")), int(record.get("toYr"))
        if last == first + 1:
            spec["period_label"] = f"FY{first}-{str(last)[-2:]}"
    except (TypeError, ValueError):
        pass
    if stamp:
        spec.update(_published_at=stamp, _precision=precision, _availability_evidence=_proof(
            res, record, "exchange_annual_report_index", f"latest explicit publication field '{field}', conservative"))
    return spec


def transcript_candidate(record: Dict, res, company: Company) -> Optional[Dict]:
    if (record.get("symbol") or "").upper() != company.symbol:
        return None
    url = _attachment(record.get("attchmntFile"))
    title = " ".join(str(record.get(k) or "") for k in ("desc", "attchmntText"))
    # A filename is only a discovery cue, never a period/publication proof.
    if not url or not re.search(r"transcript", title + " " + url, re.I):
        return None
    stamp = nse.parse_nse_timestamp(record.get("exchdisstime") or record.get("an_dt"))
    if not stamp:
        return None
    return {"url": url, "doc_type": "earnings_call_transcript", "_discovered": True,
            "_published_at": stamp, "_precision": "second", "_availability_evidence": _proof(
                res, record, "exchange_announcement", "dated exchange record listing this exact attachment")}


def discover_company_sources(store: Store, fetcher: Fetcher, settings: Settings, company: Company,
                             cutoff_utc: str, progress: Callable[[str], None] = lambda s: None,
                             deadline: Optional[float] = None) -> Dict[str, Any]:
    """Fill absent AR/transcript coverage within finite query/download bounds.

    Latest annual index, at most four 90-day announcement windows, three AR
    candidates and three transcript candidates. Stops after one usable AR and
    up to two transcripts. Inaccessible sources yield a partial report.
    """
    started = time.monotonic()
    cut = datetime.fromisoformat(cutoff_utc).astimezone(timezone.utc)
    end_day = cut.astimezone(IST).date()
    report: Dict[str, Any] = {"version": DISCOVERY_VERSION, "symbol": company.symbol,
                             "cutoff_utc": cutoff_utc, "started_at": utcnow(), "queries": [],
                             "documents": [], "issues": [], "bounds": {"announcement_windows": 4,
                             "window_days": 90, "annual_downloads": 3, "transcript_downloads": 3}}

    def time_left():
        return deadline is None or time.monotonic() < deadline

    def eligible_types():
        return classify_versions(store, company.company_id, "replay", cutoff_utc)[0]

    existing = eligible_types()
    need_ar = not any(v["doc_type"] == "annual_report" for v in existing)
    need_tr = not any(v["doc_type"] == "earnings_call_transcript" for v in existing)
    if not need_ar and not need_tr:
        return {**report, "state": "already_covered", "elapsed_seconds": 0}

    progress("discovering_sources")
    index_specs: List[Dict] = []
    if need_ar and time_left():
        res, records = nse.fetch_annual_report_index(fetcher, company)
        report["queries"].append({"source": "annual_report_index", "url": res.url,
                                  "state": res.state, "records": len(records), "error": res.error})
        if not res.ok:
            report["issues"].append(f"Annual-report index {res.state}: {res.error}")
        for rec in records:
            spec = annual_candidate(rec, res, company)
            if spec and (not spec.get("_published_at") or datetime.fromisoformat(spec["_published_at"]) <= cut):
                index_specs.append(spec)
        index_specs.sort(key=lambda s: s.get("_published_at") or "", reverse=True)

    attempts = {"annual_report": 0, "earnings_call_transcript": 0}
    tried = set()

    def ingest(spec):
        kind = spec["doc_type"]
        if spec["url"] in tried or attempts[kind] >= 3 or not time_left():
            return
        tried.add(spec["url"]); attempts[kind] += 1
        progress("downloading_sources")
        result = documents.ingest_document(store, fetcher, company, spec, max_pages=settings.max_pdf_pages)
        report["documents"].append(result)
        if result.get("state") != "fetched":
            report["issues"].append(f"{kind} {result.get('state')}: {result.get('error')}")
        elif result.get("identification", {}).get("identity_ok") is False:
            report["issues"].append(f"Rejected {kind}: source identity, type or reporting-period check failed.")

    for spec in index_specs:
        if spec.get("_published_at"):
            ingest(spec)
            if any(v["doc_type"] == "annual_report" for v in eligible_types()):
                break

    tr_found = 0
    cursor = end_day
    for _ in range(4):
        if not time_left():
            report["issues"].append("Discovery time budget reached; remaining documents were not checked.")
            break
        ar_present = any(v["doc_type"] == "annual_report" for v in eligible_types())
        if ar_present and (not need_tr or tr_found >= 2):
            break
        start = cursor - timedelta(days=89)
        progress("discovering_sources")
        res, records = nse.fetch_announcements(fetcher, company, start, cursor)
        nse.store_announcements(store, company, res, records)
        report["queries"].append({"source": "announcements", "url": res.url, "state": res.state,
                                  "records": len(records), "error": res.error})
        if not res.ok:
            report["issues"].append(f"Announcements {start}..{cursor} {res.state}: {res.error}")
        rows = []
        for rec in records:
            if (rec.get("symbol") or "").upper() != company.symbol:
                continue
            stamp = nse.parse_nse_timestamp(rec.get("exchdisstime") or rec.get("an_dt"))
            if stamp and start <= datetime.fromisoformat(stamp).astimezone(IST).date() <= cursor and datetime.fromisoformat(stamp) <= cut:
                rows.append((stamp, rec))
        rows.sort(key=lambda x: x[0], reverse=True)
        for stamp, rec in rows:
            url = _attachment(rec.get("attchmntFile"))
            if not ar_present:
                spec = next((s for s in index_specs if s["url"] == url), None)
                title = " ".join(str(rec.get(k) or "") for k in ("desc", "attchmntText"))
                if spec is None and re.search(r"annual\s+report", title, re.I) and url:
                    spec = {"url": url, "doc_type": "annual_report", "_discovered": True}
                if spec is not None:
                    spec = {**spec, "_published_at": stamp, "_precision": "second", "_availability_evidence": _proof(
                        res, rec, "exchange_announcement", "dated exchange record listing this annual-report attachment")}
                    ingest(spec)
                    ar_present = any(v["doc_type"] == "annual_report" for v in eligible_types())
            if need_tr and tr_found < 2:
                spec = transcript_candidate(rec, res, company)
                if spec:
                    before = {v["version_id"] for v in eligible_types() if v["doc_type"] == "earnings_call_transcript"}
                    ingest(spec)
                    after = {v["version_id"] for v in eligible_types() if v["doc_type"] == "earnings_call_transcript"}
                    tr_found += len(after - before)
        cursor = start - timedelta(days=1)

    documents.link_existing_versions(store, company)
    final = eligible_types()
    report["eligible"] = [{k: v[k] for k in ("version_id", "doc_type", "period_label", "published_at", "parse_status")} for v in final]
    kinds = {v["doc_type"] for v in final}
    for kind in ("annual_report", "earnings_call_transcript"):
        if kind not in kinds:
            report["issues"].append(f"No eligible {kind.replace('_', ' ')} found within the bounded discovery lookback.")
    report.update(state="completed" if {"annual_report", "earnings_call_transcript"} <= kinds else "partial",
                  elapsed_seconds=round(time.monotonic() - started, 2), finished_at=utcnow())
    return report
