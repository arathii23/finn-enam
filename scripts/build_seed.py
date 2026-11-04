#!/usr/bin/env python3
"""Build a larger seed corpus locally, in an isolated copy of the production store.

The free Render instance forgets everything it discovers (redeploy, restart, spin-down), so the
documents a user would otherwise wait minutes for can instead ship inside the Docker image's seed.
This tool reuses the SAME discovery code the live service runs (refresh mode, cutoff = now), against
a COPY of the production database; the production store is never written.

    python scripts/build_seed.py prepare  --out data/seed_build_YYYY_MM_DD
    python scripts/build_seed.py discover --out ...            # real NSE access, keyless, no model
    python scripts/build_seed.py verify   --out ...            # what changed, what did not
    python scripts/build_seed.py pack     --out ...            # tarball + manifest (nothing published)

Publishing the tarball (a GitHub Release) is a separate, reviewed step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

# Keyless and key-free regardless of the developer's shell or .env: this tool never calls a model.
for _name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY",
              "OPENROUTER_API_KEY"):
    os.environ[_name] = ""
os.environ["FINN_MODEL_PROVIDER"] = "keyless"

from finn.config import get_settings  # noqa: E402
from finn.contracts import ResearchRequest  # noqa: E402
from finn.db import Store  # noqa: E402
from finn.discovery import discover_company_sources  # noqa: E402
from finn.replay import load_manifest  # noqa: E402
from finn.research import run_research  # noqa: E402
from finn.service import App  # noqa: E402
from finn.sources import nse  # noqa: E402
from finn.sources.fetch import Fetcher  # noqa: E402

PRODUCTION_DB = REPO / "data" / "finn.sqlite3"
PRODUCTION_SOURCES = REPO / "data" / "sources"
QUESTION = "What guidance did management give for revenue growth and margins, and what conditions came with it?"


def portfolio_symbols() -> List[str]:
    return json.loads((REPO / "manifests" / "portfolio.json").read_text())["symbols"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_db(src: Path, dst: Path) -> None:
    """Consistent copy through SQLite's backup API (never a raw file copy of a live database)."""
    a, b = sqlite3.connect(src), sqlite3.connect(dst)
    try:
        a.backup(b)
    finally:
        b.close()
        a.close()


def build_settings(out: Path):
    return replace(get_settings(), data_dir=out.resolve())


# --------------------------------------------------------------------------- prepare
def cmd_prepare(args) -> int:
    out = Path(args.out)
    if out.exists():
        print(f"refusing to overwrite existing {out}", file=sys.stderr)
        return 2
    out.mkdir(parents=True)
    backup_db(PRODUCTION_DB, out / "baseline.sqlite3")      # frozen reference for verify
    backup_db(PRODUCTION_DB, out / "finn.sqlite3")          # the copy discovery will write into
    # Clone-on-write copy on APFS (instant, no extra disk); plain copy elsewhere.
    cloned = subprocess.run(["cp", "-cR", str(PRODUCTION_SOURCES), str(out / "sources")], capture_output=True)
    if cloned.returncode != 0:
        shutil.copytree(PRODUCTION_SOURCES, out / "sources")
    meta = {"prepared_at": datetime.now(timezone.utc).isoformat(),
            "baseline_sha256": sha256_file(out / "baseline.sqlite3"),
            "git_commit": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                                         text=True).stdout.strip()}
    (out / "build_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    return 0


# --------------------------------------------------------------------------- discover
def cmd_discover(args) -> int:
    out = Path(args.out)
    s = build_settings(out)
    store = Store(s.db_path, s.files_dir)
    cutoff = datetime.now(timezone.utc).isoformat()
    reports = out / "reports"
    reports.mkdir(exist_ok=True)
    symbols = [x.upper() for x in args.symbols] or portfolio_symbols()
    fetcher = Fetcher(store, max_bytes=s.max_download_bytes)
    failed = 0
    try:
        for symbol in symbols:
            t0 = time.monotonic()
            try:
                company = nse.resolve_company(store, symbol, fetcher)
                report = discover_company_sources(store, fetcher, s, company, cutoff, refresh=True)
            except Exception as exc:  # noqa: BLE001 - a failed company is reported, never hidden
                report = {"symbol": symbol, "state": "error", "issues": [f"{exc.__class__.__name__}: {exc}"]}
            report["wall_seconds"] = round(time.monotonic() - t0, 1)
            (reports / f"discovery_{symbol}.json").write_text(json.dumps(report, indent=2, default=str))
            state = report.get("state")
            failed += state not in ("completed", "already_covered")
            print(f"{symbol:11s} {state:16s} {report['wall_seconds']:>6}s  "
                  f"{'; '.join((report.get('issues') or [])[:2])[:110]}", flush=True)
    finally:
        fetcher.close()
    print(f"done: {len(symbols) - failed}/{len(symbols)} companies completed")
    return 0 if not failed else 2


# --------------------------------------------------------------------------- verify
VOLATILE_KEYS = {"resolved_at"}   # regenerated on every identity lookup; not evidence


def _strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def canon(obj: Any) -> str:
    return hashlib.sha256(json.dumps(_strip_volatile(obj), sort_keys=True, default=str).encode()).hexdigest()


def doc_rows(db: Path) -> Dict[str, Dict[str, Any]]:
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        return {r["version_id"]: dict(r) for r in c.execute(
            "SELECT version_id, company_id, doc_type, period_label, source_url, content_hash, page_count, "
            "published_at, availability_status, parse_status, parser_version FROM document_versions")}
    finally:
        c.close()


def replay_views(settings, symbols: List[str]) -> Dict[str, str]:
    """Hash every replay read model the static snapshot and replay UI depend on."""
    app = App(settings, start_worker=False)
    views: Dict[str, str] = {}
    for window in ("24h", "7d", "all"):
        views[f"portfolio_{window}"] = canon(app.portfolio_queue(mode="replay", window=window))
    for sym in symbols:
        ov = app.company_overview(sym, "replay")
        views[f"{sym}:announcements"] = canon(ov["announcements"])
        views[f"{sym}:eod"] = canon(ov["eod"])
        views[f"{sym}:eligible_docs"] = canon(sorted(d["version_id"] for d in ov["documents"]["eligible"]))
        views[f"{sym}:excluded_docs"] = canon(sorted(d["version_id"] for d in ov["documents"]["excluded"]))
        for name, fn in (("narrative", app.narrative_numbers), ("quarterly", app.quarterly_results),
                         ("management", app.management_changes)):
            views[f"{sym}:{name}"] = canon(fn(sym, "replay"))
    return views


def cmd_verify(args) -> int:
    out = Path(args.out)
    s = build_settings(out)
    symbols = portfolio_symbols()
    problems: List[str] = []
    base, built = doc_rows(out / "baseline.sqlite3"), doc_rows(out / "finn.sqlite3")

    # 1. Nothing that existed may have changed.
    for vid, row in base.items():
        if vid not in built:
            problems.append(f"baseline document missing from build: {vid}")
        elif built[vid] != row:
            problems.append(f"baseline document row changed: {vid}")
    new = {vid: r for vid, r in built.items() if vid not in base}

    # 2. Saved research is untouched.
    def jobs(db):
        c = sqlite3.connect(db)
        try:
            return canon(c.execute("SELECT job_id, state, result FROM jobs ORDER BY job_id").fetchall())
        finally:
            c.close()
    jobs_same = jobs(out / "baseline.sqlite3") == jobs(out / "finn.sqlite3")
    if not jobs_same:
        problems.append("saved jobs differ from the baseline")

    # 3. Replay read models, on throwaway copies so the build and baseline stay unmodified.
    with tempfile.TemporaryDirectory() as tmp:
        t_base, t_new = Path(tmp) / "base", Path(tmp) / "new"
        for t, src in ((t_base, "baseline.sqlite3"), (t_new, "finn.sqlite3")):
            t.mkdir()
            backup_db(out / src, t / "finn.sqlite3")
            (t / "sources").mkdir()
        before, after = replay_views(replace(s, data_dir=t_base), symbols), replay_views(replace(s, data_dir=t_new), symbols)
    changed = sorted(k for k in before if before[k] != after.get(k))
    expected_growth = [k for k in changed if k.endswith(":excluded_docs")]
    unexpected = [k for k in changed if k not in expected_growth]
    if unexpected:
        problems.append(f"replay read models changed unexpectedly: {unexpected}")

    # 4. New documents: identity/publication status, and exact quotes from a keyless current brief.
    status: Dict[str, int] = {}
    for r in new.values():
        key = f"{r['doc_type']}/{r['availability_status']}/{r['parse_status']}"
        status[key] = status.get(key, 0) + 1
    store = Store(s.db_path, s.files_dir)
    cfg = load_manifest(s.manifest_path)
    quotes_ok = quotes_bad = 0
    brief_rows = []
    for sym in symbols:
        company = nse.resolve_company(store, sym)
        _, o = run_research(store, s, cfg, company, ResearchRequest(symbol=sym, question=QUESTION, mode="live"),
                            None, None, lambda _x: None)
        sb = o.source_brief
        n = 0
        for h in (sb.highlights if sb else []):
            p = store.query_one("SELECT text FROM passages WHERE passage_id=?", (h.evidence_id,))
            if p and h.quote.rstrip("…").strip() in p["text"]:
                quotes_ok += 1
            else:
                quotes_bad += 1
                problems.append(f"{sym}: highlight is not an exact substring of {h.evidence_id}")
            n += 1
        latest = max((e.get("published_at") or "" for e in o.evidence_index.values()
                      if e.get("doc_type") == "earnings_call_transcript"), default="")
        brief_rows.append((sym, n, latest[:10]))
    report = {"verified_at": datetime.now(timezone.utc).isoformat(),
              "baseline_documents": len(base), "build_documents": len(built), "new_documents": len(new),
              "new_by_type_status": status, "saved_jobs_identical": jobs_same,
              "replay_views_compared": len(before), "replay_views_changed": changed,
              "expected_growth_excluded_lists": len(expected_growth),
              "keyless_brief_quotes_exact": quotes_ok, "keyless_brief_quotes_not_exact": quotes_bad,
              "briefs": [{"symbol": a, "highlights": b, "latest_transcript_published": c} for a, b, c in brief_rows],
              "problems": problems}
    (out / "verify_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "replay_views_changed"}, indent=2))
    print("replay views changed (expected only excluded-document lists):", changed[:20])
    return 0 if not problems else 3


# --------------------------------------------------------------------------- pack
def cmd_pack(args) -> int:
    out = Path(args.out)
    stage = out / "pack"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    src = sqlite3.connect(out / "finn.sqlite3")
    try:
        src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        src.execute(f"VACUUM INTO '{stage / 'finn.sqlite3'}'")   # compact, consistent, no WAL
    finally:
        src.close()
    shutil.copytree(out / "sources", stage / "sources")
    files = sorted(p for p in (stage / "sources").rglob("*") if p.is_file())
    meta = json.loads((out / "build_meta.json").read_text())
    c = sqlite3.connect(stage / "finn.sqlite3")
    counts = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("companies", "document_versions", "passages", "announcements", "jobs")}
    c.close()
    manifest = {"seed_built_at": datetime.now(timezone.utc).isoformat(), "source_commit": meta.get("git_commit"),
                "baseline_sha256": meta.get("baseline_sha256"), "counts": counts,
                "database_sha256": sha256_file(stage / "finn.sqlite3"),
                "source_files": {str(p.relative_to(stage)): sha256_file(p) for p in files}}
    (stage / "SEED_MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    tarball = out / "finn-seed.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(stage / "finn.sqlite3", arcname="finn.sqlite3")
        tar.add(stage / "sources", arcname="sources")
        tar.add(stage / "SEED_MANIFEST.json", arcname="SEED_MANIFEST.json")
    size = tarball.stat().st_size
    print(json.dumps({"tarball": str(tarball), "bytes": size, "mb": round(size / 1e6, 1), "counts": counts,
                      "source_files": len(files), "sha256": sha256_file(tarball)}, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("prepare", cmd_prepare), ("discover", cmd_discover), ("verify", cmd_verify), ("pack", cmd_pack)):
        sp = sub.add_parser(name)
        sp.add_argument("--out", required=True, help="build directory (inside the git-ignored data/ folder)")
        if name == "discover":
            sp.add_argument("symbols", nargs="*", help="NSE symbols (default: the 15 portfolio holdings)")
        sp.set_defaults(fn=fn)
    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
