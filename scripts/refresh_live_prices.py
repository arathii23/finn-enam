#!/usr/bin/env python3
"""Fetch free live EOD for the portfolio from Yahoo Finance and write live_prices.json.

Runs in GitHub Actions on a schedule (no server, no key, stdlib only). The output JSON has the
same shape the app's /api/live-prices returns, so the static site renders it directly and shows
a "last updated" timestamp. Raw (unadjusted) prices; a move is never attributed to a filing.
"""
from __future__ import annotations

import argparse
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.NS?range=3mo&interval=1d"
HEADERS = {"User-Agent": "Mozilla/5.0 (FINN primary-source research prototype)"}
REPO_ROOT = Path(__file__).resolve().parents[1]


def _eod_anomaly(rows: List[Dict[str, Any]], price_move_pct: float, volume_multiple: float,
                 baseline_sessions: int, min_baseline: int) -> Optional[Dict[str, Any]]:
    """Mirror of finn.prioritize.eod_anomaly: flag the latest session on raw values."""
    rows = [r for r in rows if r.get("close") is not None]
    if not rows:
        return None
    latest, prior = rows[-1], rows[:-1]
    flags, notes = [], []
    price_move = None
    if latest.get("prev_close"):
        price_move = (latest["close"] - latest["prev_close"]) / latest["prev_close"] * 100.0
        if abs(price_move) >= price_move_pct:
            flags.append(f"price move {price_move:+.1f}% ≥ ±{price_move_pct:g}%")
    else:
        notes.append("no previous close; price-move check skipped")
    vol_ratio = None
    vols = [r["volume"] for r in prior if r.get("volume")][-baseline_sessions:]
    if latest.get("volume") and len(vols) >= min_baseline:
        base = mean(vols)
        if base > 0:
            vol_ratio = latest["volume"] / base
            if vol_ratio >= volume_multiple:
                flags.append(f"volume {vol_ratio:.1f}× the {len(vols)}-session average ≥ {volume_multiple:g}×")
    else:
        notes.append(f"insufficient volume history (<{min_baseline} prior sessions); volume ratio disabled")
    return {"trading_date": latest["trading_date"], "close": latest["close"],
            "prev_close": latest.get("prev_close"), "volume": latest.get("volume"),
            "price_move_pct": round(price_move, 2) if price_move is not None else None,
            "volume_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
            "flags": flags, "flagged": bool(flags), "basis": "raw (unadjusted) EOD", "notes": notes}


def _fetch(symbol: str) -> Dict[str, Any]:
    url = CHART_URL.format(ticker=symbol.upper())
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"symbol": symbol, "state": "error", "error": f"Yahoo HTTP {exc.code}"}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"symbol": symbol, "state": "error", "error": f"transport error: {exc.__class__.__name__}"}
    try:
        result = payload["chart"]["result"][0]
        meta, stamps, q = result["meta"], result["timestamp"], result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError):
        return {"symbol": symbol, "state": "error", "error": "unexpected Yahoo response shape"}
    rows, prev = [], None
    for i, ts in enumerate(stamps):
        close = q.get("close", [None])[i] if i < len(q.get("close", [])) else None
        if close is None:
            continue
        date = datetime.fromtimestamp(ts, timezone.utc).astimezone(
            timezone(__import__("datetime").timedelta(hours=5, minutes=30))).date().isoformat()
        rows.append({"trading_date": date, "close": close, "prev_close": prev,
                     "volume": q.get("volume", [None])[i] if i < len(q.get("volume", [])) else None})
        prev = close
    if not rows:
        return {"symbol": symbol, "state": "error", "error": "no price rows"}
    return {"symbol": symbol, "state": "ok", "currency": meta.get("currency"),
            "exchange": meta.get("fullExchangeName"), "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="live_prices.json")
    ap.add_argument("--portfolio", default=str(REPO_ROOT / "manifests" / "portfolio.json"))
    args = ap.parse_args(argv)
    pf = json.loads(Path(args.portfolio).read_text())
    d = pf.get("anomaly_defaults", {})
    pmp, vmul = float(d.get("price_move_pct", 5.0)), float(d.get("volume_multiple", 2.0))
    base, minb = int(d.get("baseline_sessions", 20)), int(d.get("min_baseline_sessions", 5))
    companies, flagged = [], 0
    for symbol in pf.get("symbols", []):
        data = _fetch(symbol)
        if data["state"] != "ok":
            companies.append({"symbol": symbol, "state": data["state"], "error": data.get("error")})
            continue
        anomaly = _eod_anomaly(data["rows"], pmp, vmul, base, minb)
        if anomaly and anomaly["flagged"]:
            flagged += 1
        companies.append({"symbol": symbol, "state": "ok", "currency": data["currency"],
                          "exchange": data["exchange"], "sessions": len(data["rows"]),
                          "latest": data["rows"][-1], "anomaly": anomaly})
    companies.sort(key=lambda c: (c.get("state") != "ok", not (c.get("anomaly") or {}).get("flagged"), c["symbol"]))
    out = {
        "source": "Yahoo Finance daily chart (free, no key); raw unadjusted EOD, auto-refreshed on a schedule",
        "thresholds": {"price_move_pct": pmp, "volume_multiple": vmul,
                       "baseline_sessions": base, "min_baseline_sessions": minb},
        "summary": {"companies": len(companies), "flagged": flagged,
                    "ok": sum(1 for c in companies if c.get("state") == "ok")},
        "companies": companies,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Live Yahoo EOD, auto-refreshed; separate from the verified replay corpus. "
                      "Raw prices; a move is not attributed to any filing. Markets move only during trading hours.",
    }
    Path(args.out).write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {args.out}: {out['summary']['ok']}/{out['summary']['companies']} ok, {flagged} flagged, at {out['retrieved_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
