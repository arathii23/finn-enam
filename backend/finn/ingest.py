"""Ingestion orchestrator: identity -> EOD -> announcements (+attachments) -> documents.

Every step records its attempts; one failed source never aborts the others."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from .config import Settings
from .db import Store
from .replay import ReplayConfig
from .sources import documents, nse
from .sources.fetch import Fetcher


def _days(start: str, end: str) -> List[date]:
    d, last = date.fromisoformat(start), date.fromisoformat(end)
    out = []
    while d <= last:
        out.append(d)
        d += timedelta(days=1)
    return out


def ingest_replay(store: Store, fetcher: Fetcher, settings: Settings, cfg: ReplayConfig, symbols: List[str],
                  include_negative: bool = True, log: Callable[[str], None] = print) -> Dict[str, Any]:
    report: Dict[str, Any] = {"replay_id": cfg.replay_id, "symbols": symbols, "steps": []}

    def step(name: str, **data):
        report["steps"].append({"step": name, **data})
        log(f"[{name}] " + ", ".join(f"{k}={v}" for k, v in data.items() if k not in ("identification",)))

    ok, msg = nse.refresh_security_master(store, fetcher)
    step("security_master", ok=ok, detail=msg)

    companies = []
    for sym in symbols:
        try:
            c = nse.resolve_company(store, sym)
            companies.append(c)
            step("identity", symbol=sym, legal_name=c.legal_name, isin=c.isin, series=c.series)
        except nse.IdentityError as exc:
            step("identity", symbol=sym, state=exc.state, detail=str(exc))
    if not companies:
        return report

    for day in _days(cfg.raw["eod_window"]["from"], cfg.raw["eod_window"]["to"]):
        s = nse.ingest_eod_day(store, fetcher, day, companies)
        step("eod", **s)

    manifest_companies = cfg.raw.get("companies", {})
    categories = set(cfg.raw.get("attachment_categories", []))
    max_att = int(cfg.raw.get("max_attachments_per_company", 2))
    for c in companies:
        entry = manifest_companies.get(c.symbol, {})
        # announcements in the replay filing window
        res, records = nse.fetch_announcements(fetcher, c, date.fromisoformat(cfg.filing_from), date.fromisoformat(cfg.filing_to))
        stored = nse.store_announcements(store, c, res, records)
        step("announcements", symbol=c.symbol, state=res.state, records=len(stored), error=res.error)

        # primary documents named in the manifest (identity and availability proven at ingest)
        for spec in entry.get("documents", []):
            s = documents.ingest_document(store, fetcher, c, spec, max_pages=settings.max_pdf_pages)
            step("document", symbol=c.symbol, **{k: v for k, v in s.items()})
        if include_negative:
            for spec in cfg.raw.get("negative_fixtures", {}).get(c.symbol, []):
                s = documents.ingest_document(store, fetcher, c, spec, max_pages=settings.max_pdf_pages)
                step("negative_fixture_document", symbol=c.symbol, **s)

        documents.link_existing_versions(store, c)
        # substantive announcement attachments (generic category rule, bounded count)
        window_rows = store.query(
            "SELECT * FROM announcements WHERE company_id=? AND attachment_url IS NOT NULL AND attachment_version_id IS NULL ORDER BY published_at",
            (c.company_id,),
        )
        picked = [r for r in window_rows if (r["category"] or "") in categories and r["published_at"]
                  and cfg.filing_from <= _ist_day(r["published_at"]) <= cfg.filing_to][:max_att]
        for ann in picked:
            s = documents.link_announcement_attachment(store, fetcher, c, ann, max_pages=settings.max_pdf_pages)
            step("announcement_attachment", symbol=c.symbol, category=ann["category"], **s)
    return report


def _ist_day(utc_iso: str) -> str:
    from datetime import datetime
    from .config import IST
    return datetime.fromisoformat(utc_iso).astimezone(IST).date().isoformat()
