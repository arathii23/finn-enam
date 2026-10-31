"""Milestone 1 checks against the REAL ingested corpus. Each check reports pass/fail/skip with
the evidence it examined; nothing is marked passed without being executed."""
from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

from pypdf import PdfReader

from .config import Settings
from .contracts import ResearchRequest
from .db import Store, sha256_bytes, utcnow
from .replay import ReplayConfig, announcements_in_window, classify_versions
from .research import run_research
from .sources import nse


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


class Checks:
    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def run(self, cid: str, name: str, fn: Callable[[], Dict[str, Any]]):
        try:
            out = fn()
        except Exception as exc:  # noqa: BLE001
            out = {"status": "fail", "detail": f"check raised {exc.__class__.__name__}: {exc}"}
        self.results.append({"id": cid, "name": name, **out})


def run_checks(store: Store, settings: Settings, cfg: ReplayConfig, symbol: str = "INFY") -> Dict[str, Any]:
    checks = Checks()
    entry = cfg.raw["companies"].get(symbol, {})
    expected = entry.get("verification", {})
    state: Dict[str, Any] = {}

    def identity():
        c = nse.resolve_company(store, symbol)
        state["company"] = c
        mismatches = {k: (getattr(c, k), v) for k, v in expected.items() if not k.startswith("_") and getattr(c, k) != v}
        ok = not mismatches and c.identity_source_url == nse.EQUITY_LIST_URL and len(c.identity_source_hash) == 64
        return {"status": "pass" if ok else "fail",
                "detail": {"resolved": c.model_dump(), "mismatches": mismatches}}

    checks.run("M1-01", "Company identity resolves from NSE security master", identity)

    def documents():
        c = state["company"]
        rows = []
        all_ok = True
        for spec in entry.get("documents", []):
            v = store.query_one("SELECT * FROM document_versions WHERE company_id=? AND source_url=?", (c.company_id, spec["url"]))
            if not v:
                rows.append({"url": spec["url"], "ok": False, "problem": "not ingested"})
                all_ok = False
                continue
            path = store.file_path(v["content_hash"])
            data = path.read_bytes() if path else b""
            ident = json.loads(v["identification"])
            problems = []
            if not data.startswith(b"%PDF-"):
                problems.append("cached file missing or not a PDF")
            if data and sha256_bytes(data) != v["content_hash"]:
                problems.append("hash mismatch")
            if not ident.get("identity_ok"):
                problems.append(f"identification failed: {ident}")
            if v["parse_status"] == "failed":
                problems.append("extraction failed")
            for f in ("source_url", "content_hash", "retrieved_at", "period_label"):
                if not v.get(f):
                    problems.append(f"missing {f}")
            all_ok &= not problems
            rows.append({"doc_type": v["doc_type"], "period": v["period_label"], "url": v["source_url"],
                         "hash": v["content_hash"], "pages": v["page_count"], "parse_status": v["parse_status"],
                         "published_at": v["published_at"], "precision": v["published_precision"],
                         "availability": v["availability_status"], "identification": ident, "problems": problems})
        return {"status": "pass" if all_ok and rows else "fail", "detail": rows}

    checks.run("M1-02", "Annual report and transcripts fetched, hashed and identified", documents)

    def announcement():
        c = state["company"]
        anns = announcements_in_window(store, c.company_id, cfg)
        with_att = [a for a in anns if a.get("attachment_version_id")]
        detail = {"records_in_window": len(anns), "attachments_fetched": [
            {"category": a["category"], "published_at_raw": a["published_at_raw"], "attachment_url": a["attachment_url"],
             "version_id": a["attachment_version_id"]} for a in with_att]}
        return {"status": "pass" if anns and with_att else "fail", "detail": detail}

    checks.run("M1-03", "Exchange announcement with its underlying filing", announcement)

    def eod():
        c = state["company"]
        rows = store.query("SELECT trading_date, close, prev_close, volume, validation_status, source_url, source_hash FROM market_observations "
                           "WHERE symbol=? AND series=? AND trading_date BETWEEN ? AND ? ORDER BY trading_date",
                           (c.symbol, c.series, cfg.raw["eod_window"]["from"], cfg.raw["eod_window"]["to"]))
        bad = [r for r in rows if r["validation_status"] != "valid" or r["close"] is None or r["volume"] is None]
        return {"status": "pass" if rows and not bad else "fail", "detail": {"rows": rows, "invalid": bad}}

    checks.run("M1-04", "Historical EOD price/volume rows", eod)

    def cutoff():
        c = state["company"]
        eligible, excluded = classify_versions(store, c.company_id, "replay", cfg.cutoff_utc)
        cut = datetime.fromisoformat(cfg.cutoff_utc)
        leaks = [v["version_id"] for v in eligible if not v["published_at"] or datetime.fromisoformat(v["published_at"]) > cut
                 or v["availability_status"] != "verified"]
        negatives = []
        for spec in cfg.raw.get("negative_fixtures", {}).get(symbol, []):
            v = store.query_one("SELECT version_id FROM document_versions WHERE company_id=? AND source_url=?", (c.company_id, spec["url"]))
            if v:
                ex = next((x for x in excluded if x["version_id"] == v["version_id"]), None)
                negatives.append({"url": spec["url"], "excluded": bool(ex), "reasons": ex["exclusion_reasons"] if ex else None})
            else:
                negatives.append({"url": spec["url"], "excluded": None, "reasons": ["not ingested; negative fixture not exercised"]})
        # Earlier-cutoff probe: 22 Apr 2025 21:00 IST precedes the Q4 transcript's dissemination.
        early = datetime(2025, 4, 22, 15, 30, tzinfo=timezone.utc).isoformat()
        e_elig, _ = classify_versions(store, c.company_id, "replay", early)
        early_types = [(v["doc_type"], v["period_label"], v["published_at"]) for v in e_elig]
        q4_in_early = any(v["doc_type"] == "earnings_call_transcript" and v["period_label"] == "Q4 FY2024-25" for v in e_elig)
        q4_in_main = any(v["doc_type"] == "earnings_call_transcript" and v["period_label"] == "Q4 FY2024-25" for v in eligible)
        # A missing negative fixture has not exercised the cutoff and cannot pass.
        neg_ok = all(n["excluded"] is True for n in negatives)
        ok = not leaks and neg_ok and not q4_in_early and q4_in_main
        return {"status": "pass" if ok else "fail", "detail": {
            "cutoff_utc": cfg.cutoff_utc, "eligible": [(v["doc_type"], v["period_label"], v["published_at"]) for v in eligible],
            "excluded": [(v["doc_type"], v["period_label"], v["exclusion_reasons"]) for v in excluded],
            "leaks": leaks, "negative_fixtures": negatives,
            "earlier_cutoff_probe": {"cutoff_utc": early, "eligible": early_types, "q4_transcript_excluded": not q4_in_early},
            "q4_transcript_eligible_at_main_cutoff": q4_in_main}}

    checks.run("M1-05", "Replay publication cutoff (incl. earlier-cutoff probe and FY25 AR negative)", cutoff)

    def citations():
        c = state["company"]
        req = ResearchRequest(symbol=symbol, mode="replay")
        job_state, out = run_research(store, settings, cfg, c, req, None if not settings.model_configured else _client(store, settings), None, lambda s: None)
        state["research"] = (job_state, out)
        ids = set(out.business_context.candidate_evidence_ids) | set(out.management_commentary.candidate_evidence_ids)
        for claim in out.business_context.claims + out.management_commentary.claims:
            ids |= set(claim.evidence_ids)
        checked, failures = [], []
        readers: Dict[str, PdfReader] = {}
        for pid in sorted(ids):
            p = store.query_one("SELECT * FROM passages WHERE passage_id=?", (pid,))
            v = store.query_one("SELECT * FROM document_versions WHERE version_id=?", (p["version_id"],))
            if v["version_id"] not in out.eligible_version_ids:
                failures.append({"passage_id": pid, "problem": "cited passage is outside the eligible corpus"})
                continue
            if v["content_hash"] not in readers:
                readers[v["content_hash"]] = PdfReader(io.BytesIO(store.file_path(v["content_hash"]).read_bytes()))
            page_text = readers[v["content_hash"]].pages[p["page_index"] - 1].extract_text() or ""
            probe = _norm(p["text"])[:200]
            ok = probe in _norm(page_text)
            checked.append({"passage_id": pid, "doc_type": v["doc_type"], "pdf_page": p["page_index"], "text_on_page": ok})
            if not ok:
                failures.append({"passage_id": pid, "problem": "passage text not found on stated PDF page"})
        status = "pass" if checked and not failures else "fail"
        return {"status": status, "detail": {"research_state": job_state, "generation": out.generation.model_dump(),
                                             "checked": checked, "failures": failures,
                                             "note": "Without a model, this verifies retrieved evidence passages; generated-claim citation checks need a configured model."}}

    checks.run("M1-06", "Citation/page accuracy: passages re-located on their PDF page", citations)

    def research_state():
        if "research" not in state:
            return {"status": "fail", "detail": "research did not run"}
        job_state, out = state["research"]
        sections_ok = out.business_context.candidate_evidence_ids and out.management_commentary.candidate_evidence_ids
        generated = out.generation.status == "generated" and out.follow_up.status == "generated"
        status = "pass" if generated and sections_ok and job_state == "completed" else ("partial" if sections_ok else "fail")
        return {"status": status, "detail": {"state": job_state, "generation": out.generation.model_dump(),
                                             "business_context_passages": len(out.business_context.candidate_evidence_ids),
                                             "commentary_passages": len(out.management_commentary.candidate_evidence_ids),
                                             "gaps": [g.text for g in out.evidence_gaps],
                                             "follow_up": out.follow_up.model_dump()}}

    checks.run("M1-07", "Bounded research view (context, commentary, gaps, follow-up)", research_state)

    summary = {s: sum(1 for r in checks.results if r["status"] == s) for s in ("pass", "partial", "fail", "skip")}
    return {"generated_at": utcnow(), "symbol": symbol, "replay_id": cfg.replay_id,
            "model_configured": settings.model_configured, "summary": summary, "checks": checks.results}


def _client(store: Store, settings: Settings):
    from .llm import create_model_client
    return create_model_client(settings, store)


def write_report(report: Dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "m1_checks.json").write_text(json.dumps(report, indent=2, default=str))
    lines = [f"# FINN M1 data checks — {report['generated_at']}", "",
             f"Model configured: {report['model_configured']}. Summary: {report['summary']}", ""]
    for r in report["checks"]:
        lines.append(f"- **{r['id']} {r['status'].upper()}** — {r['name']}")
    path = out_dir / "m1_checks.md"
    path.write_text("\n".join(lines) + "\n")
    return path
