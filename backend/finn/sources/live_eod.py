"""Live end-of-day prices from Yahoo Finance's free public chart API (no key, no library).

The PDF names yfinance as the usual starting point and says "anything equivalent works". We
call Yahoo's chart JSON directly over the existing httpx stack — equivalent, free and lean (no
pandas). This is deliberately separate from the verified April-2025 replay corpus: live rows
are never written into the replay store, and the UI labels them as live Yahoo EOD. Prices are
raw (unadjusted); a move is never presented as caused by a filing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List, Optional

import httpx

from ..config import IST
from ..prioritize import eod_anomaly

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (FINN primary-source research prototype)"}


def _yahoo_ticker(symbol: str, series: str = "EQ") -> str:
    # Portfolio holdings are NSE equities; Yahoo uses the .NS suffix for NSE.
    return f"{symbol.strip().upper()}.NS"


def fetch_live_eod(symbol: str, client: httpx.Client, range_: str = "3mo") -> Dict[str, Any]:
    """Fetch recent daily OHLCV for one NSE symbol. Returns rows ascending by date, or an error."""
    ticker = _yahoo_ticker(symbol)
    try:
        resp = client.get(CHART_URL.format(ticker=ticker), params={"range": range_, "interval": "1d"},
                           headers=_HEADERS, timeout=httpx.Timeout(15.0, connect=8.0))
    except httpx.HTTPError as exc:
        return {"symbol": symbol, "state": "error", "error": f"transport error: {exc.__class__.__name__}"}
    if resp.status_code != 200:
        return {"symbol": symbol, "state": "error", "error": f"Yahoo HTTP {resp.status_code}"}
    try:
        chart = resp.json()["chart"]
        if chart.get("error"):
            return {"symbol": symbol, "state": "not_found", "error": str(chart["error"])}
        result = chart["result"][0]
        meta = result["meta"]
        stamps = result["timestamp"]
        q = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError, ValueError):
        return {"symbol": symbol, "state": "error", "error": "unexpected Yahoo response shape"}

    rows: List[Dict[str, Any]] = []
    prev_close: Optional[float] = None
    for i, ts in enumerate(stamps):
        close = q.get("close", [None] * len(stamps))[i]
        if close is None:
            continue
        date = datetime.fromtimestamp(ts, timezone.utc).astimezone(IST).date().isoformat()
        rows.append({
            "trading_date": date,
            "open": q.get("open", [None])[i], "high": q.get("high", [None])[i],
            "low": q.get("low", [None])[i], "close": close,
            "prev_close": prev_close, "volume": q.get("volume", [None])[i],
        })
        prev_close = close
    return {
        "symbol": symbol, "state": "ok", "ticker": ticker,
        "currency": meta.get("currency"), "exchange": meta.get("fullExchangeName"),
        "rows": rows, "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": CHART_URL.format(ticker=ticker),
    }


def live_market_snapshot(symbols: List[str], client: httpx.Client, price_move_pct: float,
                         volume_multiple: float, baseline_sessions: int = 20,
                         min_baseline: int = 5) -> Dict[str, Any]:
    """Fetch live EOD for each symbol and flag unusual moves with the same deterministic rule
    used on replay data. Expensive calls are bounded: one bounded request per symbol."""
    companies: List[Dict[str, Any]] = []
    flagged = 0
    for symbol in symbols:
        data = fetch_live_eod(symbol, client)
        if data["state"] != "ok" or not data["rows"]:
            companies.append({"symbol": symbol, "state": data["state"],
                              "error": data.get("error") or "no price rows returned"})
            continue
        anomaly = eod_anomaly(data["rows"], price_move_pct, volume_multiple, baseline_sessions, min_baseline)
        if anomaly and anomaly["flagged"]:
            flagged += 1
        companies.append({"symbol": symbol, "state": "ok", "currency": data["currency"],
                          "exchange": data["exchange"], "sessions": len(data["rows"]),
                          "latest": data["rows"][-1], "anomaly": anomaly,
                          "source_url": data["source_url"], "retrieved_at": data["retrieved_at"]})
    companies.sort(key=lambda c: (c.get("state") != "ok", not (c.get("anomaly") or {}).get("flagged"), c["symbol"]))
    return {
        "source": "Yahoo Finance daily chart (free, no key); raw unadjusted EOD",
        "thresholds": {"price_move_pct": price_move_pct, "volume_multiple": volume_multiple,
                       "baseline_sessions": baseline_sessions, "min_baseline_sessions": min_baseline},
        "summary": {"companies": len(companies), "flagged": flagged,
                    "ok": sum(1 for c in companies if c.get("state") == "ok")},
        "companies": companies,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Live Yahoo EOD, separate from the verified replay corpus. Raw prices; a move is not attributed to any filing.",
    }
