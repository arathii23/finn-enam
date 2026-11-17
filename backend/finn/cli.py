"""Command line: `python -m finn <command>` (run from backend/)."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from dataclasses import replace

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
        print("Refusing to export: select FINN_MODEL_PROVIDER=keyless so the snapshot is model-free.")
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


def cmd_xbrl_refresh(args) -> int:
    """Explicitly cache recent integrated-filing XBRL; this command never invokes an AI model."""
    from .service import App
    app = App(get_settings(), start_worker=False)
    report = app.refresh_financials(args.symbols or None, args.quarters)
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["state"] == "completed" else 2


def cmd_alerts(args) -> int:
    """Explicitly check current sources and send leading filing/EOD alerts to ntfy."""
    from . import alerts
    from .sources import nse
    from .service import App

    # Alerts are deterministic and remain model-free regardless of shell/.env keys.
    s = replace(get_settings(), model_provider="keyless")
    app = App(s, start_worker=False)
    symbols = [x.upper() for x in (args.symbols or app.portfolio.get("symbols", []))]
    if not symbols:
        print("No portfolio symbols are configured.", file=sys.stderr)
        return 2

    # A clean GitHub runner has no local security-master cache. Resolve the public
    # NSE master once before the bounded current filing check.
    if not app.store.query_one("SELECT 1 FROM security_master LIMIT 1"):
        fetcher = app.fetcher_factory()
        try:
            nse.refresh_security_master(app.store, fetcher)
        finally:
            fetcher.close()

    from .current import refresh_portfolio_sources
    refresh = refresh_portfolio_sources(app.store, s, symbols, app.fetcher_factory, args.days)
    queue = app.portfolio_queue(mode="live", window="7d")
    prices = json.loads(Path(args.prices).read_text()) if args.prices and Path(args.prices).is_file() else (
        {} if args.prices else app.live_prices(symbols=symbols))
    checked = {row["symbol"] for row in refresh.get("companies", []) if row.get("state") == "fetched"}
    candidates = alerts.build_notifications(queue, prices, checked_symbols=checked,
                                           extra_categories=alerts.categories_from_env(args.categories),
                                           now=datetime.now(timezone.utc), days=args.days)
    state_path = Path(args.state).expanduser() if args.state else s.data_dir / "alerts_state.json"
    state = alerts.load_state(state_path)
    pending = alerts.pending_notifications(candidates, state)
    outcomes = {"sent": [], "failed": [], "filing_delay_seconds": []}

    if args.dry_run:
        print(json.dumps({"dry_run": True, "refresh": refresh, "candidates": pending,
                          "pending": len(pending), "state_written": False}, indent=2, default=str))
    else:
        topic = args.topic or os.environ.get("NTFY_TOPIC", "")
        next_state, outcomes = alerts.send_pending(pending, state, topic=topic)
        alerts.save_state(state_path, next_state)
        print(json.dumps({"dry_run": False, "refresh": refresh, "candidates": len(candidates),
                          "sent": len(outcomes["sent"]), "failed": outcomes["failed"],
                          "state_file": str(state_path)}, indent=2, default=str))

    if args.status_out:
        status = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "refresh_state": refresh.get("state"), "holdings_checked": refresh.get("checked", 0),
                  "holdings_total": len(refresh.get("companies", [])), "pending": len(pending),
                  "sent": len(outcomes["sent"]), "failed": len(outcomes["failed"]),
                  "filing_delay_seconds": outcomes["filing_delay_seconds"],
                  "dry_run": bool(args.dry_run),
                  "cadence_note": "GitHub's free scheduler is best-effort; checks may be minutes to hours apart."}
        Path(args.status_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.status_out).write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    return 2 if outcomes["failed"] else 0


def cmd_digest(args) -> int:
    import httpx
    from .digest import build_digest, read_previous, write_atomic
    from .service import App

    previous = None
    try:
        if args.previous:
            previous = read_previous(args.previous)
        app = App(replace(get_settings(), model_provider="keyless"), start_worker=False)
        app.refresh_current_portfolio(args.days)
        digest = build_digest(app.portfolio_queue(mode="live", window="7d"), previous=previous)
        if args.out:
            write_atomic(Path(args.out), digest)
    except (OSError, ValueError, httpx.HTTPError) as exc:
        print(f"Digest failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"generated_at": digest["generated_at"], "checked": digest["checks"]["holdings_checked"],
                      "items": len(digest["items"]), "model_calls": 0, "out": args.out}))
    return 0 if digest["checks"]["holdings_checked"] else 2


def cmd_eval(args) -> int:
    from .evaluation import FrozenSeed, evaluate, write_report

    report = evaluate(FrozenSeed(Path(args.db)), get_settings())
    write_report(report, Path(args.out))
    for name, check in report["checks"].items():
        print(f"{name}: {check['passed']}/{check['total']} passed, {check.get('not_run', 0)} not run")
    print(f"Report: {Path(args.out).resolve()}")
    return 2 if any(check["failures"] for check in report["checks"].values()) else 0


def cmd_calendar(args) -> int:
    from .calendar_feed import refresh_calendar
    from .sources.fetch import Fetcher

    settings = get_settings()
    symbols = json.loads(settings.portfolio_path.read_text())["symbols"]
    store = Store(settings.db_path, settings.files_dir)
    fetcher = Fetcher(store, max_bytes=min(2 * 1024 * 1024, settings.max_download_bytes))
    try:
        count = refresh_calendar(fetcher, symbols, Path(args.out), datetime.now(timezone.utc))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        fetcher.close()
    print(f"Wrote {count} upcoming NSE portfolio events to {args.out}")
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
    xf = sub.add_parser("xbrl-refresh", help="read NSE integrated financial-result XBRL (no model call)")
    xf.add_argument("symbols", nargs="*", help="NSE symbols (default: all portfolio holdings)")
    xf.add_argument("--quarters", type=int, default=8, help="recent quarter ends to retain per basis (1–12)")
    xf.set_defaults(fn=cmd_xbrl_refresh)
    al = sub.add_parser("alerts", help="dry-run or send deterministic current filing and EOD alerts to ntfy")
    al.add_argument("symbols", nargs="*", help="NSE symbols (default: portfolio holdings)")
    al.add_argument("--days", type=int, default=7, choices=range(1, 8), help="recent NSE filing window (1–7 days)")
    al.add_argument("--categories", help="additional category slugs to include, comma-separated")
    al.add_argument("--state", help="deduplication state JSON path")
    al.add_argument("--status-out", help="optional latest-check summary JSON path")
    al.add_argument("--prices", help="read EOD flags from a saved live_prices.json instead of fetching")
    al.add_argument("--topic", help="ntfy topic (otherwise read NTFY_TOPIC from the environment)")
    al.add_argument("--dry-run", action="store_true", help="list notifications without sending or updating state")
    al.set_defaults(fn=cmd_alerts)
    dg = sub.add_parser("digest", help="build a local, keyless subject-line portfolio digest")
    dg.add_argument("--days", type=int, choices=[7], default=7)
    dg.add_argument("--out", help="local JSON output path")
    dg.add_argument("--previous", help="previous digest path or configured public feed URL")
    dg.add_argument("--dry-run", action="store_true", help="run the same checks without any publication (this CLI only writes locally)")
    dg.set_defaults(fn=cmd_digest)
    ev = sub.add_parser("eval", help="evaluate keyless research on a checkpointed local seed")
    ev.add_argument("--db", required=True, help="path to the frozen seed SQLite file (opened read-only)")
    ev.add_argument("--out", required=True, help="directory to write eval_report.json and README.md")
    ev.set_defaults(fn=cmd_eval)
    calendar = sub.add_parser("calendar", help="build a local .ics file from NSE future events")
    calendar.add_argument("--out", required=True, help="path to write finn-events.ics")
    calendar.set_defaults(fn=cmd_calendar)
    srv = sub.add_parser("serve")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    srv.set_defaults(fn=cmd_serve)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
