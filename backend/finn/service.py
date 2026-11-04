"""Framework-free application service used by the FastAPI routes and by tests."""
from __future__ import annotations

import json
import queue
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .compare import build_narrative_numbers
from .config import IST, PROMPT_VERSION, Settings
from .contracts import Gap, ResearchRequest
from .discovery import discover_company_sources
from .db import Store, new_id, sha256_bytes, utcnow
from .llm import ResponsesClient, create_model_client
from .replay import ReplayConfig, announcements_in_window, classify_versions, load_manifest
from .prioritize import classify, eod_anomaly
from . import management, quarterly
from .research import run_research
from .sources import documents, nse
from .sources.fetch import Fetcher

STAGES = ["resolving_company", "discovering_sources", "downloading_sources", "finding_documents", "reading_sources", "preparing_research"]
RESEARCH_PIPELINE_VERSION = "practical-source-context-2026-11-04"
SOURCE_REFRESH_CACHE_S = 15 * 60


def _fiscal_end_year(cutoff_utc: Optional[str]) -> int:
    """End-year of the Indian fiscal year (Apr–Mar) in progress at the cutoff.

    A guidance for that year or later has no known outcome yet, so it is shown as pending.
    """
    from datetime import datetime
    dt = datetime.fromisoformat(cutoff_utc).astimezone(IST) if cutoff_utc else datetime.now(IST)
    return dt.year + 1 if dt.month >= 4 else dt.year


class NotFound(Exception):
    def __init__(self, state: str, message: str):
        super().__init__(message)
        self.state = state


class App:
    def __init__(self, settings: Settings, store: Optional[Store] = None, client: Optional[ResponsesClient] = None,
                 start_worker: bool = True, fetcher_factory=None):
        self.settings = settings
        self.store = store or Store(settings.db_path, settings.files_dir)
        self.replay: Optional[ReplayConfig] = load_manifest(settings.manifest_path) if settings.manifest_path.exists() else None
        self.portfolio: Dict[str, Any] = json.loads(settings.portfolio_path.read_text()) if settings.portfolio_path.exists() else {"symbols": []}
        self.client = client if client is not None else (create_model_client(settings, self.store) if settings.model_configured else None)
        self._queue: "queue.Queue[str]" = queue.Queue(maxsize=20)
        self._submission_lock = threading.Lock()
        self._current_refresh_lock = threading.Lock()
        self.fetcher_factory = fetcher_factory or (lambda: Fetcher(self.store, max_bytes=settings.max_download_bytes))
        self._mark_interrupted()
        if start_worker:
            threading.Thread(target=self._worker, name="finn-research-worker", daemon=True).start()

    # ------------------------------------------------------------ status
    def health(self) -> Dict[str, Any]:
        counts = self.store.query_one(
            "SELECT (SELECT COUNT(*) FROM companies) AS companies, (SELECT COUNT(*) FROM document_versions) AS documents,"
            " (SELECT COUNT(*) FROM passages) AS passages, (SELECT COUNT(*) FROM announcements) AS announcements,"
            " (SELECT COUNT(*) FROM market_observations) AS eod_rows, (SELECT COUNT(*) FROM security_master) AS security_master_rows"
        )
        return {
            "status": "ok",
            "model_configured": self.settings.model_configured,
            "model_provider": self.settings.model_provider,
            "model_primary": self.settings.model_primary,
            "capabilities": {"keyless_research": True, "current_source_research": True,
                             "source_refresh": "explicit_research_request", "refresh_cache_seconds": SOURCE_REFRESH_CACHE_S},
            "replay": self.replay_info(),
            "corpus": counts,
            "frontend_built": (self.settings.frontend_dist / "index.html").exists(),
        }

    def replay_info(self) -> Optional[Dict[str, Any]]:
        if not self.replay:
            return None
        r = self.replay
        return {"replay_id": r.replay_id, "label": r.label, "filing_from": r.filing_from, "filing_to": r.filing_to,
                "cutoff_utc": r.cutoff_utc, "cutoff_display": r.cutoff_display,
                "prepared_symbols": sorted(r.raw.get("companies", {}).keys())}

    # ------------------------------------------------------------ company
    def company(self, symbol: str) -> Dict[str, Any]:
        try:
            c = nse.resolve_company(self.store, symbol)
        except nse.IdentityError as exc:
            raise NotFound(exc.state, str(exc)) from exc
        return c.model_dump()

    def company_overview(self, symbol: str, mode: str = "replay") -> Dict[str, Any]:
        company = self.company(symbol)
        cid = company["company_id"]
        cfg = self.replay if mode == "replay" else None
        eligible, excluded = classify_versions(self.store, cid, mode, cfg.cutoff_utc if cfg else None)
        anns = announcements_in_window(self.store, cid, cfg)
        eod_q = "SELECT * FROM market_observations WHERE symbol=? AND series=?"
        params: tuple = (company["symbol"], company["series"])
        if cfg:
            eod_q += " AND trading_date BETWEEN ? AND ?"
            params += (cfg.raw["eod_window"]["from"], cfg.raw["eod_window"]["to"])
        eod = self.store.query(eod_q + " ORDER BY trading_date", params)
        attempts = self.store.query(
            "SELECT source_kind, state, COUNT(*) AS n, MAX(finished_at) AS last FROM fetch_attempts"
            " WHERE company_id=? OR company_id IS NULL GROUP BY source_kind, state ORDER BY source_kind", (cid,))
        return {
            "company": company, "mode": mode, "replay": self.replay_info() if cfg else None,
            "announcements": [self._ann_public(a) for a in anns],
            "eod": eod,
            "documents": {"eligible": [self._ver_public(v) for v in eligible], "excluded": [self._ver_public(v) for v in excluded]},
            "coverage": attempts,
            "freshness": self._source_freshness(cid, eligible),
        }

    def _source_freshness(self, company_id: str, versions: List[Dict]) -> Dict[str, Any]:
        attempt = self.store.query_one("SELECT state,finished_at FROM fetch_attempts WHERE company_id=? "
                                       "AND source_kind IN ('nse_announcements','nse_annual_report_index') ORDER BY finished_at DESC LIMIT 1", (company_id,))
        return {"latest_publication": max((v.get("published_at") or "" for v in versions), default=None) or None,
                "last_checked": attempt["finished_at"] if attempt else None,
                "state": attempt["state"] if attempt else "not_checked",
                "note": "Stored evidence; a current research request checks primary sources explicitly. A source-check time is not a document publication date."}

    def coverage(self) -> Dict[str, Any]:
        rows = self.store.query("SELECT * FROM fetch_attempts ORDER BY started_at DESC LIMIT 300")
        return {"attempts": rows}

    # ------------------------------------------------------------ evidence
    def evidence(self, passage_id: str) -> Dict[str, Any]:
        p = self.store.query_one("SELECT * FROM passages WHERE passage_id=?", (passage_id,))
        if not p:
            raise NotFound("not_found", "passage not found")
        v = self.store.query_one("SELECT * FROM document_versions WHERE version_id=?", (p["version_id"],))
        company = self.store.query_one("SELECT * FROM companies WHERE company_id=?", (v["company_id"],))
        neighbours = self.store.query(
            "SELECT passage_id, seq, substr(text,1,400) AS text FROM passages WHERE version_id=? AND page_index=? AND passage_id<>? ORDER BY seq",
            (p["version_id"], p["page_index"], passage_id))
        return {"passage": {**p, "printed_page_reason": None if p["printed_page"] else "not identified by parser"},
                "document": self._ver_public({**v, "identification": json.loads(v["identification"])}),
                "company": company, "same_page_passages": neighbours}

    def document(self, version_id: str) -> Dict[str, Any]:
        v = self.store.query_one("SELECT * FROM document_versions WHERE version_id=?", (version_id,))
        if not v:
            raise NotFound("not_found", "document version not found")
        return self._ver_public({**v, "identification": json.loads(v["identification"])})

    # ------------------------------------------------------------ quarterly results first cut (Push)
    def management_changes(self, symbol: str, mode: str = "replay") -> Dict[str, Any]:
        """Eligible appointment context, including clearly labelled pre-window filings."""
        company = self.company(symbol)
        cfg = self.replay if mode == "replay" else None
        eligible, _ = classify_versions(self.store, company["company_id"], mode, cfg.cutoff_utc if cfg else None)
        filings = {v["version_id"]: v for v in eligible if v["doc_type"] == "exchange_filing"}
        in_window = {a["announcement_id"] for a in announcements_in_window(self.store, company["company_id"], cfg)}
        anns = self.store.query("SELECT * FROM announcements WHERE company_id=? ORDER BY published_at DESC, announcement_id", (company["company_id"],))
        items, seen = [], set()
        for a in anns:
            vid = a.get("attachment_version_id")
            if vid not in filings or vid in seen:
                continue
            if cfg:
                try:
                    stamp = datetime.fromisoformat(a.get("published_at") or "")
                except (TypeError, ValueError):
                    continue
                if stamp.tzinfo is None or stamp > datetime.fromisoformat(cfg.cutoff_utc):
                    continue
            if classify(a.get("category"), a.get("subject"))["ref_category"] != "management_change":
                continue
            rows = self.store.query("SELECT passage_id, text, page_index FROM passages WHERE version_id=? ORDER BY page_index, seq", (vid,))
            item = management.extract_appointment(a.get("subject") or "", rows)
            if item:
                seen.add(vid)
                items.append({**item, "announcement_id": a["announcement_id"], "version_id": vid,
                              "published_at": filings[vid]["published_at"],
                              "in_review_window": a["announcement_id"] in in_window})
            if len(items) == 3:
                break
        return {"symbol": company["symbol"], "mode": mode, "served": "deterministic", "items": items,
                "method": "Quotes from eligible appointment filings already in the corpus; not a complete management history.",
                "empty_reason": None if items else "No named appointment with a verified role, date and brief profile could be read from the eligible filings."}

    def quarterly_results(self, symbol: str, mode: str = "replay", force: bool = False,
                          allow_extract: bool = False) -> Dict[str, Any]:
        """Read/revalidate saved results by default; extraction needs explicit opt-in."""
        try:
            company = nse.resolve_company(self.store, symbol)
        except nse.IdentityError as exc:
            raise NotFound(exc.state, str(exc)) from exc
        cfg = self.replay if mode == "replay" else None
        eligible, _ = classify_versions(self.store, company.company_id, mode, cfg.cutoff_utc if cfg else None)
        filings = [v for v in eligible if v["doc_type"] == "exchange_filing"]
        base = {"symbol": company.symbol, "legal_name": company.legal_name, "mode": mode}
        if not filings:
            return {**base, "available": False, "can_extract": False, "extraction_required": False,
                    "reason": "No eligible results filing is stored for this company."}
        ph = ",".join("?" * len(filings))
        rows = self.store.query(
            f"SELECT passage_id, version_id, page_index, text FROM passages WHERE version_id IN ({ph}) ORDER BY version_id, page_index, seq",
            tuple(v["version_id"] for v in filings))
        meta = {v["version_id"]: v for v in filings}
        passages = [{**r, "doc_type": "exchange_filing"} for r in rows]
        selected = quarterly.select_pnl_passages(passages)
        selected_version = selected[0]["version_id"] if selected else None
        fp = sha256_bytes(json.dumps(sorted(p["passage_id"] for p in selected)).encode())[:16]
        key = f"quarterly:{company.company_id}:{quarterly.VALIDATION_VERSION}:{fp}"

        if not force and selected_version:
            # Legacy caches retain their original bytes. Revalidate their recorded
            # figures against eligible source pages in memory, without another call.
            cached_rows = self.store.query(
                "SELECT cache_key, result FROM derived_cache WHERE kind='quarterly' AND cache_key LIKE ? ORDER BY created_at DESC",
                (f"quarterly:{company.company_id}:%",))
            cached_rows.sort(key=lambda r: r["cache_key"] != key)
            by_id = {p["passage_id"]: p for p in passages if p["version_id"] == selected_version}
            for cached_row in cached_rows:
                saved = json.loads(cached_row["result"])
                if ((saved.get("source") or {}).get("version_id") != selected_version
                        and not (cached_row["cache_key"] == key and not saved.get("metrics"))):
                    continue
                if not saved.get("metrics"):
                    return {**base, **saved, "served": "cached", "can_extract": False,
                            "extraction_required": False, "validation_version": quarterly.VALIDATION_VERSION}
                # An unavailable or cross-version citation cannot enter validation.
                safe = {**saved, "metrics": [m for m in saved.get("metrics", []) if m.get("evidence_id") in by_id]}
                source_passages = list(by_id.values())
                checked = quarterly.validate_and_compute(quarterly.cached_extraction(safe),
                            {pid: p["text"] for pid, p in by_id.items()}, quarterly.page_contexts(source_passages))
                for metric in checked["metrics"]:
                    p = by_id[metric["evidence_id"]]
                    v = meta[p["version_id"]]
                    metric["source"] = {"version_id": p["version_id"], "page_index": p["page_index"],
                                        "published_at": v.get("published_at"), "period_label": v.get("period_label")}
                source = checked["metrics"][0]["source"] if checked["metrics"] else saved.get("source")
                return {**base, **checked, "available": bool(checked["metrics"]), "served": "cached",
                        "generation": saved.get("generation"), "source": source,
                        "can_extract": False, "extraction_required": False,
                        **({"reason": "The saved extraction contains no figures that pass the current source checks."}
                           if not checked["metrics"] else {})}
        if not selected:
            return {**base, "available": False, "can_extract": False, "extraction_required": False,
                    "reason": "No dated quarterly statement could be identified in the stored filings."}
        configured = self.client is not None and self.settings.model_configured
        if not allow_extract:
            return {**base, "available": False, "can_extract": configured, "extraction_required": True,
                    "reason": "The filing is stored; a quarterly extraction has not been saved yet."}
        if not configured:
            return {**base, "available": False, "can_extract": False, "extraction_required": True,
                    "reason": "New extraction is unavailable. The stored primary filing remains accessible."}

        result = self._extract_quarterly(company, selected, meta)
        # Completed abstentions are cached; transient provider/budget failures remain retryable.
        if result.get("available") or result.get("generation"):
            self.store.execute("INSERT OR REPLACE INTO derived_cache (cache_key, kind, result, created_at) VALUES (?,?,?,?)",
                               (key, "quarterly", json.dumps(result), utcnow()))
        return {**base, **result}

    def _extract_quarterly(self, company, selected, meta) -> Dict[str, Any]:
        from .llm import BudgetExceeded, ModelUnavailable
        if len({p["version_id"] for p in selected}) != 1:
            return {"available": False, "reason": "Extraction requires a single source filing."}
        def esc(t): return (t or "").replace("<", "‹").replace(">", "›")
        lines = [f"Company: {company.legal_name} (NSE: {company.symbol})"]
        for p in selected:
            lines.append(f'<statement id="{p["passage_id"]}" page="{p["page_index"]}">\n{esc(p["text"])}\n</statement>')
        model = "claude-haiku-5-5" if self.settings.model_provider == "anthropic" else self.settings.model_primary
        try:
            res = self.client.generate(job_id=None, model=model, effort="low", system=quarterly.SYSTEM_PROMPT,
                                       user="\n".join(lines), schema=quarterly.EXTRACT_SCHEMA,
                                       schema_name="finn_quarterly", max_output_tokens=2200)
        except (ModelUnavailable, BudgetExceeded) as exc:
            return {"available": False, "can_extract": self.settings.model_configured, "extraction_required": True,
                    "reason": f"Extraction did not run: {exc}"}
        if res.status != "completed" or res.data is None:
            return {"available": False, "can_extract": True, "extraction_required": True,
                    "reason": f"Table extraction failed: {res.error or res.status}."}
        by_id = {p["passage_id"]: p for p in selected}
        computed = quarterly.validate_and_compute(res.data, {pid: p["text"] for pid, p in by_id.items()},
                                                   quarterly.page_contexts(selected))
        for metric in computed["metrics"]:
            p = by_id[metric["evidence_id"]]
            v = meta[p["version_id"]]
            metric["source"] = {"version_id": p["version_id"], "page_index": p["page_index"],
                                "published_at": v.get("published_at"), "period_label": v.get("period_label")}
        first = selected[0]
        v = meta[first["version_id"]]
        source = computed["metrics"][0]["source"] if computed["metrics"] else {
            "version_id": first["version_id"], "page_index": first["page_index"],
            "period_label": v.get("period_label"), "published_at": v.get("published_at")}
        return {"available": bool(computed["metrics"]), "served": "generated", "source": source,
                "generation": {"model": model, "usage": res.usage}, "can_extract": False,
                "extraction_required": False, **computed,
                **({"reason": "No headline figures passed verification against the filing."} if not computed["metrics"] else {})}

    # ------------------------------------------------------------ numbers vs narrative (Pull)
    def narrative_numbers(self, symbol: str, mode: str = "replay") -> Dict[str, Any]:
        """Deterministic promised-vs-delivered view from eligible transcripts and filings."""
        try:
            company = nse.resolve_company(self.store, symbol)
        except nse.IdentityError as exc:
            raise NotFound(exc.state, str(exc)) from exc
        cfg = self.replay if mode == "replay" else None
        cutoff = cfg.cutoff_utc if cfg else None
        eligible, _ = classify_versions(self.store, company.company_id, mode, cutoff)
        versions = [v for v in eligible if v["doc_type"] in ("earnings_call_transcript", "exchange_filing")]
        management: set = set()
        for v in versions:
            if v["doc_type"] == "earnings_call_transcript":
                management.update((v.get("identification") or {}).get("management_speakers") or [])

        passages: List[Dict[str, Any]] = []
        meta = {v["version_id"]: v for v in versions}
        if versions:
            ph = ",".join("?" * len(versions))
            rows = self.store.query(
                f"SELECT passage_id, version_id, page_index, speaker, text FROM passages WHERE version_id IN ({ph}) ORDER BY version_id, seq",
                tuple(meta))
            for r in rows:
                v = meta[r["version_id"]]
                passages.append({**r, "doc_type": v["doc_type"], "period_label": v.get("period_label"),
                                 "published_at": v.get("published_at")})

        result = build_narrative_numbers(company.symbol, company.legal_name, passages,
                                         cfg.cutoff_display if cfg else None,
                                         cutoff_end_year=_fiscal_end_year(cutoff), management=management)
        # Evidence index so the UI can label and open each cited passage, same as research.
        idx = {}
        for p in passages:
            v = meta[p["version_id"]]
            idx[p["passage_id"]] = {"version_id": p["version_id"], "doc_type": p["doc_type"],
                                    "period_label": v.get("period_label"), "page_index": p["page_index"],
                                    "speaker": p.get("speaker"), "published_at": v.get("published_at"),
                                    "excerpt": (p["text"] or "")[:280]}
        result.update(company=company.model_dump(), mode=mode, cutoff=cutoff, evidence_index=idx,
                      sources=[{"version_id": v["version_id"], "doc_type": v["doc_type"],
                                "period_label": v.get("period_label")} for v in versions])
        return result

    def document_file(self, version_id: str) -> Path:
        v = self.store.query_one("SELECT content_hash FROM document_versions WHERE version_id=?", (version_id,))
        if not v:
            raise NotFound("not_found", "document version not found")
        path = self.store.file_path(v["content_hash"])
        if not path:
            raise NotFound("file_missing", "cached file is missing; use the original link")
        return path

    # ------------------------------------------------------------ research jobs
    def submit_research(self, req: ResearchRequest) -> Dict[str, Any]:
        with self._submission_lock:
            return self._submit_research(req)

    def _research_key(self, req: ResearchRequest, company_id: str) -> str:
        cfg = self.replay if req.mode == "replay" else None
        eligible, _ = classify_versions(self.store, company_id, req.mode, cfg.cutoff_utc if cfg else None)
        return sha256_bytes(json.dumps([req.symbol, req.question, req.event_id, req.mode, cfg.cutoff_utc if cfg else None,
                                      sorted((v["version_id"], v["parser_version"]) for v in eligible), self.settings.model_configured,
                                      self.settings.model_provider, self.settings.model_primary, PROMPT_VERSION,
                                      RESEARCH_PIPELINE_VERSION, int(time.time() // SOURCE_REFRESH_CACHE_S) if req.mode == "live" else None]).encode())

    def _submit_research(self, req: ResearchRequest) -> Dict[str, Any]:
        symbol = req.symbol.strip().upper()
        req = req.model_copy(update={"symbol": symbol})
        company = self.company(symbol)  # raises NotFound for unknown symbols before queuing
        if req.event_id:
            event = self.store.query_one("SELECT company_id FROM announcements WHERE announcement_id=?", (req.event_id,))
            if not event or event["company_id"] != company["company_id"]:
                raise NotFound("invalid_event", "This filing is not available for the selected company. Open the company and choose a stored filing.")
        # Discovery changes the corpus while a job runs. Deduplicate its input
        # independently of that evolving fingerprint before looking up caches.
        for pending in self.store.query("SELECT job_id,request FROM jobs WHERE state IN ('queued','running')"):
            previous = json.loads(pending["request"])
            if all(previous.get(k) == req.model_dump().get(k) for k in ("symbol", "question", "event_id", "mode")):
                return {"job_id": pending["job_id"], "reused": True}
        key = self._research_key(req, company["company_id"])
        existing = self.store.query_one(
            "SELECT job_id,state,result FROM jobs WHERE idempotency_key=? AND state IN ('queued','running','completed','partial') ORDER BY created_at DESC,rowid DESC LIMIT 1",
            (key,))
        if existing:
            generation = json.loads(existing["result"] or "{}").get("generation", {})
            # Explicit retries can recover transient budget/provider failures.
            # Keep completed results and in-flight work deduplicated; do not
            # repeatedly spend on unchanged missing evidence.
            recoverable = existing["state"] == "partial"
            if not (req.retry and recoverable):
                return {"job_id": existing["job_id"], "reused": True}
        job_id = new_id("job")
        now = utcnow()
        self.store.insert("jobs", {"job_id": job_id, "kind": "research", "idempotency_key": key, "state": "queued",
                                   "stage": None, "stages": json.dumps([]), "request": req.model_dump_json(),
                                   "result": None, "error": None, "created_at": now, "updated_at": now})
        try:
            self._queue.put_nowait(job_id)
        except queue.Full:
            self.store.execute("UPDATE jobs SET state='failed', error=? WHERE job_id=?", ("research queue is full; retry shortly", job_id))
        return {"job_id": job_id, "reused": False}

    def job(self, job_id: str) -> Dict[str, Any]:
        row = self.store.query_one("SELECT * FROM jobs WHERE job_id=?", (job_id,))
        if not row:
            raise NotFound("not_found", "job not found")
        row["stages"] = json.loads(row["stages"])
        row["request"] = json.loads(row["request"])
        row["result"] = json.loads(row["result"]) if row["result"] else None
        row["all_stages"] = STAGES
        return row

    def saved_research(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Discover persisted generated results without submitting a research job."""
        items = []
        for row in self.store.query("SELECT job_id,state,result FROM jobs WHERE result IS NOT NULL AND state IN ('completed','partial') ORDER BY updated_at DESC,rowid DESC LIMIT 100"):
            result = json.loads(row["result"])
            company = result.get("company") or {}
            kind = "ai_brief" if result.get("generation", {}).get("status") == "generated" else "source_brief"
            if kind == "source_brief" and not (result.get("source_brief") or {}).get("highlights"):
                continue
            if symbol and company.get("symbol") != symbol.strip().upper():
                continue
            items.append({"job_id": row["job_id"], "state": row["state"],
                          "symbol": company.get("symbol"), "legal_name": company.get("legal_name"),
                          "question": result.get("question"), "event_id": (result.get("event") or {}).get("announcement_id"),
                          "mode": result.get("mode"), "generated_at": result.get("generated_at"),
                          "kind": kind, "provider": result.get("generation", {}).get("model"),
                          "document_count": len(result.get("eligible_version_ids") or [])})
        return {"items": items}

    def run_job(self, job_id: str) -> None:
        row = self.store.query_one("SELECT * FROM jobs WHERE job_id=?", (job_id,))
        req = ResearchRequest(**json.loads(row["request"]))
        stages: List[Dict[str, Any]] = []
        t0 = time.monotonic()

        def progress(stage: str):
            now = utcnow()
            if stages:
                stages[-1]["finished_at"] = now
            stages.append({"stage": stage, "started_at": now, "finished_at": None})
            if time.monotonic() - t0 > self.settings.research_deadline_s:
                raise TimeoutError(f"research deadline of {self.settings.research_deadline_s}s exceeded at {stage}")
            self.store.execute("UPDATE jobs SET state='running', stage=?, stages=?, updated_at=? WHERE job_id=?",
                               (stage, json.dumps(stages), now, job_id))

        try:
            progress("resolving_company")
            company = nse.resolve_company(self.store, req.symbol)
            discovery = {}
            cutoff = self.replay.cutoff_utc if self.replay and req.mode == "replay" else utcnow()
            event_issue = self._read_selected_filing(company, req.event_id, cutoff, progress) if req.event_id else None
            eligible, _ = classify_versions(self.store, company.company_id, req.mode, cutoff)
            recent_discovery = self._recent_source_check(req.symbol) if req.mode == "live" else None
            if (req.mode == "live" and recent_discovery is None) or not {"annual_report", "earnings_call_transcript"} <= {v["doc_type"] for v in eligible}:
                fetcher = self.fetcher_factory()
                try:
                    discovery = discover_company_sources(self.store, fetcher, self.settings, company, cutoff,
                                                         progress, t0 + self.settings.research_deadline_s - 15,
                                                         refresh=req.mode == "live")
                finally:
                    fetcher.close()
                # The completed result must use the discovered corpus key, or
                # opening it again would unnecessarily create a second model job.
                self.store.execute("UPDATE jobs SET idempotency_key=? WHERE job_id=?",
                                   (self._research_key(req, company.company_id), job_id))
            elif recent_discovery:
                discovery = {**recent_discovery, "cached": True,
                             "cache_note": "Reused the last primary-source check within 15 minutes; the question was retrieved separately."}
            self.store.execute("UPDATE jobs SET idempotency_key=? WHERE job_id=?",
                               (self._research_key(req, company.company_id), job_id))
            state, output = run_research(self.store, self.settings, self.replay, company, req, self.client, job_id, progress)
            output.discovery = discovery
            for issue in discovery.get("issues", []):
                output.evidence_gaps.append(Gap(kind="coverage", text=issue))
            if event_issue:
                output.evidence_gaps.append(Gap(kind="coverage", text=event_issue))
            stages[-1]["finished_at"] = utcnow()
            self.store.execute("UPDATE jobs SET state=?, stage='done', stages=?, result=?, updated_at=? WHERE job_id=?",
                               (state, json.dumps(stages), output.model_dump_json(), utcnow(), job_id))
        except Exception as exc:  # noqa: BLE001 - job failures are reported, never hidden
            if stages:
                stages[-1]["finished_at"] = utcnow()
            self.store.execute("UPDATE jobs SET state='failed', stages=?, error=?, updated_at=? WHERE job_id=?",
                               (json.dumps(stages), f"{exc.__class__.__name__}: {exc}", utcnow(), job_id))

    def _read_selected_filing(self, company, event_id: str, cutoff: str, progress) -> Optional[str]:
        """Download only the filing deliberately selected by the user, never on page open."""
        row = self.store.query_one("SELECT * FROM announcements WHERE announcement_id=? AND company_id=?", (event_id, company.company_id))
        if not row or row.get("attachment_version_id"):
            return None
        if not row.get("attachment_url") or not row.get("published_at"):
            return "The selected filing has no dated attachment to retrieve; its exchange metadata remains available."
        if datetime.fromisoformat(row["published_at"]) > datetime.fromisoformat(cutoff):
            return "The selected filing was published after the chosen source cutoff and was excluded."
        progress("downloading_sources")
        spec = {"url": row["attachment_url"], "doc_type": "exchange_filing",
                "_published_at": row["published_at"], "_precision": "second",
                "_availability_evidence": [{"method": "exchange_announcement", "source_url": row["source_url"],
                    "source_hash": row.get("source_hash"), "matched_record": json.loads(row["raw_json"]),
                    "note": "Dated exchange record listing this exact selected attachment."}]}
        fetcher = self.fetcher_factory()
        try:
            result = documents.ingest_document(self.store, fetcher, company, spec, max_pages=self.settings.max_pdf_pages)
            if result.get("version_id"):
                self.store.execute("UPDATE announcements SET attachment_version_id=?,attachment_state=? WHERE announcement_id=?",
                                   (result["version_id"], result["state"], event_id))
        finally:
            fetcher.close()
        linked = self.store.query_one("SELECT attachment_version_id FROM announcements WHERE announcement_id=?", (event_id,))
        eligible, _ = classify_versions(self.store, company.company_id, "replay", cutoff)
        if (result.get("state") != "fetched" or not linked or not linked["attachment_version_id"] or
                linked["attachment_version_id"] not in {v["version_id"] for v in eligible}):
            return "The selected filing could not be read and linked to this company; inspect the original exchange attachment."
        return None

    def _recent_source_check(self, symbol: str) -> Optional[Dict[str, Any]]:
        from .discovery import DISCOVERY_VERSION
        for row in self.store.query("SELECT request,result FROM jobs WHERE result IS NOT NULL ORDER BY updated_at DESC LIMIT 100"):
            request = json.loads(row["request"])
            if request.get("symbol") != symbol or request.get("mode") != "live":
                continue
            discovery = json.loads(row["result"]).get("discovery") or {}
            if discovery.get("version") != DISCOVERY_VERSION:
                continue
            stamp = discovery.get("finished_at")
            if stamp and 0 <= (datetime.now(IST) - datetime.fromisoformat(stamp)).total_seconds() < SOURCE_REFRESH_CACHE_S:
                return discovery
        return None

    def refresh_current_portfolio(self, days: int = 7) -> Dict[str, Any]:
        from .current import refresh_portfolio_sources
        if not self._current_refresh_lock.acquire(blocking=False):
            raise NotFound("refresh_running", "A filing check is already running. Try the review again shortly.")
        try:
            return refresh_portfolio_sources(self.store, self.settings, self.portfolio.get("symbols", []), self.fetcher_factory, days)
        finally:
            self._current_refresh_lock.release()

    def _worker(self) -> None:
        while True:
            job_id = self._queue.get()
            self.run_job(job_id)

    def _mark_interrupted(self) -> None:
        self.store.execute("UPDATE jobs SET state='interrupted', error='server restarted before completion; resubmit to retry' "
                           "WHERE state IN ('queued','running')")
        # A parser/prompt correction must not leave older research snapshots
        # looking current while their page chunks or attribution have changed.
        for row in self.store.query("SELECT job_id, result FROM jobs WHERE result IS NOT NULL AND state IN ('completed','partial')"):
            if json.loads(row["result"]).get("generation", {}).get("prompt_version") != PROMPT_VERSION:
                self.store.execute("UPDATE jobs SET state='interrupted', result=NULL, error=? WHERE job_id=?",
                                   ("Research rules changed; run again to refresh source attribution and evidence.", row["job_id"]))

    # ------------------------------------------------------------ portfolio queue (Push)
    def portfolio_queue(self, mode: str = "replay", price_move_pct: Optional[float] = None,
                        volume_multiple: Optional[float] = None, window: str = "24h",
                        filing_from: Optional[str] = None, filing_to: Optional[str] = None) -> Dict[str, Any]:
        cfg = self.replay if mode == "replay" else None
        # Window controls filter the stored corpus; they never imply a live poll.
        end = datetime.fromisoformat(cfg.cutoff_utc).astimezone(IST) if cfg else datetime.now(IST)
        earliest = datetime.fromisoformat(cfg.filing_from + "T00:00:00+05:30") if cfg else None
        if window == "custom":
            try:
                start = datetime.fromisoformat((filing_from or "") + "T00:00:00+05:30")
                end = datetime.fromisoformat((filing_to or "") + "T23:59:59+05:30")
            except ValueError:
                raise ValueError("Choose both review dates in YYYY-MM-DD format.")
            if start > end:
                raise ValueError("The start date must be on or before the end date.")
            if cfg and (start < earliest or end > datetime.fromisoformat(cfg.cutoff_utc)):
                raise ValueError(f"Stored replay coverage is {cfg.filing_from} to {cfg.filing_to}; choose dates inside it.")
        elif window in ("24h", "7d"):
            start = end - timedelta(days=1 if window == "24h" else 7) + timedelta(seconds=1)
            if mode == "live" and window == "7d":
                # The explicit seven-day exchange check uses seven IST calendar
                # dates. Do not imply it also covered an earlier partial eighth day.
                start = (end - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
            if earliest:
                start = max(start, earliest)
        elif window == "all":
            start = earliest
        else:
            raise ValueError("Choose 24h, 7d, all or custom for the review period.")
        defaults = self.portfolio.get("anomaly_defaults", {})
        pmp = price_move_pct if price_move_pct is not None else float(defaults.get("price_move_pct", 5.0))
        vmul = volume_multiple if volume_multiple is not None else float(defaults.get("volume_multiple", 2.0))
        base = int(defaults.get("baseline_sessions", 20))
        min_base = int(defaults.get("min_baseline_sessions", 5))

        companies, checked, with_events, flagged = [], 0, 0, 0
        current_report = {}
        if mode == "live":
            from .current import read_refresh_report
            current_report = read_refresh_report(self.settings) or {}
        current_rows = {r["symbol"]: r for r in current_report.get("companies", [])}
        for symbol in self.portfolio.get("symbols", []):
            try:
                c = nse.resolve_company(self.store, symbol)
            except nse.IdentityError:
                companies.append({"symbol": symbol, "status": "unresolved",
                                  "coverage": {"identity": False, "announcements": 0, "eod": 0, "documents": 0}})
                continue
            cid = c.company_id
            anns = announcements_in_window(self.store, cid, cfg)
            anns = [a for a in anns if a.get("published_at") and
                    (start is None or datetime.fromisoformat(a["published_at"]) >= start) and
                    datetime.fromisoformat(a["published_at"]) <= end]
            docs, _ = classify_versions(self.store, cid, mode, cfg.cutoff_utc if cfg else None)
            eod_q = "SELECT * FROM market_observations WHERE symbol=? AND series=?"
            params: tuple = (c.symbol, c.series)
            if cfg:
                eod_q += " AND trading_date BETWEEN ? AND ?"
                params += (cfg.raw["eod_window"]["from"], cfg.raw["eod_window"]["to"])
            eod_q += " AND trading_date<=?"
            params += (end.date().isoformat(),)
            eod = self.store.query(eod_q + " ORDER BY trading_date", params)
            if mode == "live" and eod and (end.date() - datetime.fromisoformat(eod[-1]["trading_date"]).date()).days > 7:
                # Historical cached prices must not create a current-day alert. The
                # separately labelled Yahoo market snapshot remains available in the UI.
                eod = []

            leading, notable, routine = [], [], []
            for a in anns:
                cl = classify(a.get("category"), a.get("subject"), a.get("attachment_url"))
                item = {"announcement_id": a["announcement_id"], "category": a.get("category"),
                        "ref_category": cl["ref_category"], "reason": cl["reason"], "tier": cl["tier"],
                        "published_at": a.get("published_at"), "subject": a.get("subject"),
                        "attachment_version_id": a.get("attachment_version_id"),
                        "attachment_url": a.get("attachment_url")}
                if cl["tier"] == 1:
                    leading.append(item)
                elif cl["tier"] == 2:
                    notable.append(item)
                else:
                    routine.append(item)
            anomaly = eod_anomaly(eod, pmp, vmul, base, min_base) if eod else None

            has_data = bool(anns or eod or docs)
            current_row = current_rows.get(c.symbol, {})
            current_ok = current_row.get("state") == "fetched"
            stamp = current_row.get("checked_at") or current_report.get("finished_at")
            if mode == "live" and stamp:
                try:
                    current_ok = current_ok and 0 <= (datetime.now(IST) - datetime.fromisoformat(stamp)).total_seconds() < SOURCE_REFRESH_CACHE_S
                except (TypeError, ValueError):
                    current_ok = False
            if (has_data if mode == "replay" else current_ok):
                checked += 1
            if leading or notable:
                with_events += 1
            if anomaly and anomaly["flagged"]:
                flagged += 1
            companies.append({
                "symbol": c.symbol, "legal_name": c.legal_name, "status": "ok" if has_data or current_ok else "no_data",
                "coverage": {"identity": True, "announcements": len(anns), "eod": len(eod), "documents": len(docs)},
                "leading_events": sorted(leading, key=lambda x: x.get("published_at") or "", reverse=True),
                "notable_events": sorted(notable, key=lambda x: x.get("published_at") or "", reverse=True),
                "routine_count": len(routine), "routine_events": routine,
                "eod_anomaly": anomaly,
                "can_research": bool(docs),
                "freshness": {"state": "stale" if current_row.get("state") == "fetched" and not current_ok else current_row.get("state", "not_checked"),
                              "last_checked": current_report.get("finished_at") if current_row else None,
                              "note": current_row.get("error") or ("Exchange metadata checked; filing PDFs open at the original source." if current_ok else "Current filings have not been verified; stored sources do not establish a quiet period.")},
            })
        # Leading companies first, then by number of leading events.
        order = {"ok": 0, "no_data": 1, "unresolved": 2}
        companies.sort(key=lambda c: (order.get(c["status"], 3), -len(c.get("leading_events", [])), c["symbol"]))
        return {
            "mode": mode, "replay": self.replay_info() if cfg else None,
            "window": {"preset": window, "from": start.isoformat() if start else None, "to": end.isoformat(),
                       "filing_from": start.date().isoformat() if start else None, "filing_to": end.date().isoformat(),
                       "label": {"24h": "Last 24 hours of replay", "7d": "Last 7 days of replay", "all": "Full replay window", "custom": "Custom replay dates"}[window] if cfg else "Stored filing window",
                       "stored_only": True},
            "thresholds": {"price_move_pct": pmp, "volume_multiple": vmul,
                           "baseline_sessions": base, "min_baseline_sessions": min_base},
            "summary": {"companies": len(companies), "checked": checked,
                        "with_events": with_events, "price_volume_flagged": flagged},
            "companies": companies,
            "refresh": current_report or None,
        }

    # ------------------------------------------------------------ live EOD (free Yahoo chart API)
    def live_prices(self, price_move_pct: Optional[float] = None, volume_multiple: Optional[float] = None,
                    symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """Optional live end-of-day snapshot for the portfolio via Yahoo's free chart API.

        Deliberately separate from the verified replay: live rows are not written to the store.
        Uses the same deterministic anomaly rule and the portfolio's default thresholds.
        """
        import httpx
        from .sources.live_eod import live_market_snapshot
        syms = symbols or self.portfolio.get("symbols", [])
        defaults = self.portfolio.get("anomaly_defaults", {})
        pmp = price_move_pct if price_move_pct is not None else float(defaults.get("price_move_pct", 5.0))
        vmul = volume_multiple if volume_multiple is not None else float(defaults.get("volume_multiple", 2.0))
        base = int(defaults.get("baseline_sessions", 20))
        min_base = int(defaults.get("min_baseline_sessions", 5))
        with httpx.Client() as client:
            snap = live_market_snapshot(syms, client, pmp, vmul, base, min_base)
        return snap

    # ------------------------------------------------------------ shaping
    @staticmethod
    def _ver_public(v: Dict[str, Any]) -> Dict[str, Any]:
        ev = v.get("availability_evidence")
        return {
            "version_id": v["version_id"], "doc_type": v["doc_type"], "period_label": v.get("period_label"),
            "period_start": v.get("period_start"), "period_end": v.get("period_end"), "event_date": v.get("event_date"),
            "source_url": v["source_url"], "final_url": v.get("final_url"), "host": v["host"],
            "content_hash": v["content_hash"], "bytes": v["bytes"], "page_count": v.get("page_count"),
            "published_at": v.get("published_at"), "published_precision": v.get("published_precision"),
            "availability_status": v["availability_status"],
            "availability_evidence": json.loads(ev) if isinstance(ev, str) else ev,
            "retrieved_at": v["retrieved_at"], "parse_status": v["parse_status"], "parser_version": v["parser_version"],
            "identification": v.get("identification"), "exclusion_reasons": v.get("exclusion_reasons", []),
        }

    @staticmethod
    def _ann_public(a: Dict[str, Any]) -> Dict[str, Any]:
        return {k: a[k] for k in ("announcement_id", "category", "subject", "published_at", "published_at_raw",
                                  "attachment_url", "attachment_version_id", "attachment_state", "retrieved_at", "source_url")}
