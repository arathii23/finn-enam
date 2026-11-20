"""Read-only evidence coverage and the latest dated evaluation summary."""
from __future__ import annotations

import json

from .config import REPO_ROOT
from .db import utcnow
from .replay import classify_versions
from .sources.xbrl import latest_result_period


def build_trust_report(store, symbols, *, replay_cutoff=None):
    holdings = []
    for symbol in symbols:
        company = store.query_one("SELECT company_id FROM companies WHERE symbol=?", (symbol,))
        row = {"symbol": symbol, "annual_period": None, "transcript_date": None, "verified_roster": None,
               "results_quarter": None, "last_filings_check": None, "filings_check_state": "not_checked"}
        if company:
            company_id = company["company_id"]
            eligible, _ = classify_versions(store, company_id, "live", None)
            annual = max((v for v in eligible if v["doc_type"] == "annual_report"),
                         key=lambda v: (v["period_end"] or "", v["published_at"]), default=None)
            transcript = max((v for v in eligible if v["doc_type"] == "earnings_call_transcript"),
                              key=lambda v: (v["event_date"] or v["published_at"][:10], v["published_at"]), default=None)
            if annual:
                row["annual_period"] = annual["period_label"] or (annual["period_end"] or "")[:4] or None
            if transcript:
                row["transcript_date"] = transcript["event_date"] or transcript["published_at"][:10]
                row["verified_roster"] = bool(transcript["identification"].get("management_speakers"))
            row["results_quarter"] = latest_result_period(store, company_id)
            attempt = store.query_one("SELECT finished_at,state FROM fetch_attempts WHERE company_id=? "
                                      "AND source_kind='nse_announcements' AND finished_at IS NOT NULL "
                                      "ORDER BY finished_at DESC, started_at DESC, (state='fetched') DESC LIMIT 1", (company_id,))
            if attempt:
                row["last_filings_check"] = attempt["finished_at"]
                row["filings_check_state"] = attempt["state"]
        holdings.append(row)

    evaluation = None
    for path in sorted((REPO_ROOT / "docs" / "evaluation").glob("*/eval_report.json"), reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            evaluation = {k: report[k] for k in ("generated_at", "scope", "checks", "latency_ms", "model_cost_usd")}
            break
        except (OSError, ValueError, KeyError):
            continue
    return {"generated_at": utcnow(), "replay_cutoff": replay_cutoff, "holdings": holdings, "evaluation": evaluation}
