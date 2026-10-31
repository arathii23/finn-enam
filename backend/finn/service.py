"""Framework-free application service used by the FastAPI routes and by tests."""
from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import PROMPT_VERSION, Settings
from .contracts import Gap, ResearchRequest
from .discovery import discover_company_sources
from .db import Store, new_id, sha256_bytes, utcnow
from .llm import ResponsesClient, create_model_client
from .replay import ReplayConfig, announcements_in_window, classify_versions, load_manifest
from .prioritize import classify, eod_anomaly
from .research import run_research
from .sources import nse
from .sources.fetch import Fetcher

STAGES = ["resolving_company", "discovering_sources", "downloading_sources", "finding_documents", "reading_sources", "preparing_research"]


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
        }

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
        cfg = self.replay
        eligible, _ = classify_versions(self.store, company_id, req.mode, cfg.cutoff_utc if cfg else None)
        return sha256_bytes(json.dumps([req.symbol, req.question, req.event_id, req.mode, cfg.cutoff_utc if cfg else None,
                                      sorted((v["version_id"], v["parser_version"]) for v in eligible), self.settings.model_configured,
                                      self.settings.model_provider, self.settings.model_primary, PROMPT_VERSION]).encode())

    def _submit_research(self, req: ResearchRequest) -> Dict[str, Any]:
        symbol = req.symbol.strip().upper()
        req = req.model_copy(update={"symbol": symbol})
        company = self.company(symbol)  # raises NotFound for unknown symbols before queuing
        if req.mode == "live":
            raise NotFound("live_not_available", "Live research is not part of Milestone 1; use historical replay.")
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
            eligible, _ = classify_versions(self.store, company.company_id, req.mode, cutoff)
            if not {"annual_report", "earnings_call_transcript"} <= {v["doc_type"] for v in eligible}:
                fetcher = self.fetcher_factory()
                try:
                    discovery = discover_company_sources(self.store, fetcher, self.settings, company, cutoff,
                                                         progress, t0 + self.settings.research_deadline_s - 15)
                finally:
                    fetcher.close()
                # The completed result must use the discovered corpus key, or
                # opening it again would unnecessarily create a second model job.
                self.store.execute("UPDATE jobs SET idempotency_key=? WHERE job_id=?",
                                   (self._research_key(req, company.company_id), job_id))
            state, output = run_research(self.store, self.settings, self.replay, company, req, self.client, job_id, progress)
            output.discovery = discovery
            for issue in discovery.get("issues", []):
                output.evidence_gaps.append(Gap(kind="coverage", text=issue))
            stages[-1]["finished_at"] = utcnow()
            self.store.execute("UPDATE jobs SET state=?, stage='done', stages=?, result=?, updated_at=? WHERE job_id=?",
                               (state, json.dumps(stages), output.model_dump_json(), utcnow(), job_id))
        except Exception as exc:  # noqa: BLE001 - job failures are reported, never hidden
            if stages:
                stages[-1]["finished_at"] = utcnow()
            self.store.execute("UPDATE jobs SET state='failed', stages=?, error=?, updated_at=? WHERE job_id=?",
                               (json.dumps(stages), f"{exc.__class__.__name__}: {exc}", utcnow(), job_id))

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
                        volume_multiple: Optional[float] = None) -> Dict[str, Any]:
        cfg = self.replay if mode == "replay" else None
        defaults = self.portfolio.get("anomaly_defaults", {})
        pmp = price_move_pct if price_move_pct is not None else float(defaults.get("price_move_pct", 5.0))
        vmul = volume_multiple if volume_multiple is not None else float(defaults.get("volume_multiple", 2.0))
        base = int(defaults.get("baseline_sessions", 20))
        min_base = int(defaults.get("min_baseline_sessions", 5))

        companies, checked, with_events, flagged = [], 0, 0, 0
        for symbol in self.portfolio.get("symbols", []):
            try:
                c = nse.resolve_company(self.store, symbol)
            except nse.IdentityError:
                companies.append({"symbol": symbol, "status": "unresolved",
                                  "coverage": {"identity": False, "announcements": 0, "eod": 0, "documents": 0}})
                continue
            cid = c.company_id
            anns = announcements_in_window(self.store, cid, cfg)
            docs, _ = classify_versions(self.store, cid, mode, cfg.cutoff_utc if cfg else None)
            eod_q = "SELECT * FROM market_observations WHERE symbol=? AND series=?"
            params: tuple = (c.symbol, c.series)
            if cfg:
                eod_q += " AND trading_date BETWEEN ? AND ?"
                params += (cfg.raw["eod_window"]["from"], cfg.raw["eod_window"]["to"])
            eod = self.store.query(eod_q + " ORDER BY trading_date", params)

            leading, notable, routine = [], [], 0
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
                    routine += 1
            anomaly = eod_anomaly(eod, pmp, vmul, base, min_base) if eod else None

            has_data = bool(anns or eod or docs)
            if has_data:
                checked += 1
            if leading or notable:
                with_events += 1
            if anomaly and anomaly["flagged"]:
                flagged += 1
            companies.append({
                "symbol": c.symbol, "legal_name": c.legal_name, "status": "ok" if has_data else "no_data",
                "coverage": {"identity": True, "announcements": len(anns), "eod": len(eod), "documents": len(docs)},
                "leading_events": sorted(leading, key=lambda x: x.get("published_at") or "", reverse=True),
                "notable_events": sorted(notable, key=lambda x: x.get("published_at") or "", reverse=True),
                "routine_count": routine,
                "eod_anomaly": anomaly,
                "can_research": bool(docs),
            })
        # Leading companies first, then by number of leading events.
        order = {"ok": 0, "no_data": 1, "unresolved": 2}
        companies.sort(key=lambda c: (order.get(c["status"], 3), -len(c.get("leading_events", [])), c["symbol"]))
        return {
            "mode": mode, "replay": self.replay_info() if cfg else None,
            "thresholds": {"price_move_pct": pmp, "volume_multiple": vmul,
                           "baseline_sessions": base, "min_baseline_sessions": min_base},
            "summary": {"companies": len(companies), "checked": checked,
                        "with_events": with_events, "price_volume_flagged": flagged},
            "companies": companies,
        }

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
