"""Command line: `python -m finn <command>` (run from backend/)."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from pathlib import Path

from .config import get_settings
from .db import Store


def cmd_check_runtime(args) -> int:
    s = get_settings()
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        fts = True
    except sqlite3.OperationalError:
        fts = False
    info = {
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "fts5": fts,
        "data_dir": str(s.data_dir),
        "manifest": str(s.manifest_path),
        "frontend_built": (s.frontend_dist / "index.html").exists(),
        # presence only; the value is never printed
        "OPENAI_API_KEY_present": bool(s.openai_api_key),
        "ANTHROPIC_API_KEY_present": bool(s.anthropic_api_key),
        "model_provider": s.model_provider,
        "active_model_key_present": s.model_configured,
        "model_primary": s.model_primary,
        "model_escalation": s.model_escalation,
    }
    print(json.dumps(info, indent=2))
    return 0 if fts else 1


def cmd_ingest(args) -> int:
    from .ingest import ingest_replay
    from .replay import load_manifest
    from .sources.fetch import Fetcher

    s = get_settings()
    store = Store(s.db_path, s.files_dir)
    cfg = load_manifest(s.manifest_path)
    fetcher = Fetcher(store, max_bytes=s.max_download_bytes)
    try:
        report = ingest_replay(store, fetcher, s, cfg, [x.upper() for x in args.symbols], include_negative=not args.no_negative)
    finally:
        fetcher.close()
    out = s.data_dir / "verification"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ingest_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"ingest report: {out / 'ingest_report.json'}")
    return 0


def cmd_verify(args) -> int:
    from .replay import load_manifest
    from .verify import run_checks, write_report

    s = get_settings()
    store = Store(s.db_path, s.files_dir)
    report = run_checks(store, s, load_manifest(s.manifest_path), args.symbol.upper())
    path = write_report(report, s.data_dir / "verification")
    for r in report["checks"]:
        print(f"{r['id']} {r['status'].upper():8s} {r['name']}")
    print(f"report: {path}")
    return 0 if all(r["status"] == "pass" for r in report["checks"]) else 2


def cmd_discover(args) -> int:
    from datetime import datetime, time, timezone
    from .config import IST
    from .discovery import discover_company_sources
    from .replay import load_manifest
    from .sources import nse
    from .sources.fetch import Fetcher
    s = get_settings()
    store = Store(s.db_path, s.files_dir)
    cutoff = (datetime.combine(datetime.strptime(args.as_of, "%Y-%m-%d").date(), time(23, 59, 59), IST)
              .astimezone(timezone.utc).isoformat()) if args.as_of else load_manifest(s.manifest_path).cutoff_utc
    out = s.data_dir / "verification"
    out.mkdir(parents=True, exist_ok=True)
    statuses = []
    with_fetcher = Fetcher(store, max_bytes=s.max_download_bytes)
    try:
        for symbol in args.symbols:
            try:
                company = nse.resolve_company(store, symbol, with_fetcher)
                report = discover_company_sources(store, with_fetcher, s, company, cutoff)
            except nse.IdentityError as exc:
                report = {"symbol": symbol.upper(), "state": exc.state, "issues": [str(exc)]}
            path = out / f"discovery_{symbol.upper()}.json"
            path.write_text(json.dumps(report, indent=2))
            print(f"{symbol.upper()}: {report['state']} — {path}")
            statuses.append(report["state"])
    finally:
        with_fetcher.close()
    return 0 if all(st in ("completed", "already_covered") for st in statuses) else 2


def cmd_export_static(args) -> int:
    from .service import App
    from .snapshot import export_static
    s = get_settings()
    if s.model_configured:
        print("Refusing to export: unset OPENAI_API_KEY / ANTHROPIC_API_KEY so the snapshot is model-free.")
        return 2
    app = App(s, start_worker=False)
    out = Path(args.out).resolve()
    manifest = export_static(app, out)
    print(json.dumps(manifest, indent=2, default=str))
    print(f"static snapshot: {out}")
    return 0


def cmd_live_prices(args) -> int:
    from .service import App
    s = get_settings()
    app = App(s, start_worker=False)
    snap = app.live_prices(symbols=[x.upper() for x in args.symbols] or None)
    for c in snap["companies"]:
        if c.get("state") != "ok":
            print(f"{c['symbol']:12s} {c.get('state')}: {c.get('error','')}")
            continue
        a = c.get("anomaly") or {}
        flag = " ⚑ " + "; ".join(a.get("flags", [])) if a.get("flagged") else ""
        print(f"{c['symbol']:12s} {c['latest']['trading_date']} close {c['latest']['close']} {c.get('currency','')}{flag}")
    print(f"\n{snap['summary']['ok']}/{snap['summary']['companies']} live, {snap['summary']['flagged']} flagged — {snap['source']}")
    return 0


def cmd_serve(args) -> int:
    import uvicorn
    uvicorn.run("finn.api:get_app", factory=True, host=args.host, port=args.port, workers=1)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="finn")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check-runtime").set_defaults(fn=cmd_check_runtime)
    dis = sub.add_parser("discover", help="find primary documents from NSE records without prefilled URLs")
    dis.add_argument("symbols", nargs="+", help="NSE symbols")
    dis.add_argument("--as-of", help="publication cutoff YYYY-MM-DD (default: replay cutoff)")
    dis.set_defaults(fn=cmd_discover)
    ing = sub.add_parser("ingest", help="retrieve replay sources from NSE (needs internet)")
    ing.add_argument("symbols", nargs="*", default=["INFY"])
    ing.add_argument("--no-negative", action="store_true", help="skip negative cutoff fixtures (FY25 AR)")
    ing.set_defaults(fn=cmd_ingest)
    ver = sub.add_parser("verify", help="run M1 data checks on the ingested corpus")
    ver.add_argument("--symbol", default="INFY")
    ver.set_defaults(fn=cmd_verify)
    exp = sub.add_parser("export-static", help="write a read-only static snapshot (no backend needed to view)")
    exp.add_argument("--out", default=str((get_settings().frontend_dist.parent / "public" / "snapshot")),
                     help="output directory (default: frontend/public/snapshot)")
    exp.set_defaults(fn=cmd_export_static)
    lp = sub.add_parser("live-prices", help="free live EOD snapshot via Yahoo (separate from replay)")
    lp.add_argument("symbols", nargs="*", help="NSE symbols (default: portfolio)")
    lp.set_defaults(fn=cmd_live_prices)
    srv = sub.add_parser("serve")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    srv.set_defaults(fn=cmd_serve)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
