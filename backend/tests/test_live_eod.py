"""Live EOD via Yahoo's free chart API — parsing, prev-close chaining and anomaly flagging.

Mocked transport: no network. Confirms live rows are normalised correctly, prev_close is
chained, the deterministic anomaly rule fires, and provider failures degrade to a per-symbol
error rather than raising.
"""
import json

import httpx

from finn.sources.live_eod import fetch_live_eod, live_market_snapshot


def _chart(closes, volumes, start_ts=1_700_000_000):
    ts = [start_ts + i * 86400 for i in range(len(closes))]
    return {"chart": {"error": None, "result": [{
        "meta": {"symbol": "TEST.NS", "currency": "INR", "fullExchangeName": "NSE"},
        "timestamp": ts,
        "indicators": {"quote": [{"close": closes, "open": closes, "high": closes,
                                  "low": closes, "volume": volumes}]},
    }]}}


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_normalises_rows_and_chains_prev_close():
    def handler(req):
        return httpx.Response(200, json=_chart([100.0, 102.0, 108.0], [1000, 1100, 5000]))
    data = fetch_live_eod("TEST", _client(handler))
    assert data["state"] == "ok" and data["currency"] == "INR"
    rows = data["rows"]
    assert len(rows) == 3
    assert rows[0]["prev_close"] is None
    assert rows[1]["prev_close"] == 100.0 and rows[2]["prev_close"] == 102.0


def test_snapshot_flags_unusual_move():
    # Flat history then a +10% move on 5x volume should flag at 5% / 2x thresholds.
    closes = [100.0] * 8 + [110.0]
    volumes = [1000] * 8 + [6000]
    def handler(req):
        return httpx.Response(200, json=_chart(closes, volumes))
    snap = live_market_snapshot(["TEST"], _client(handler), price_move_pct=5.0, volume_multiple=2.0)
    c = snap["companies"][0]
    assert c["state"] == "ok" and c["anomaly"]["flagged"]
    assert snap["summary"]["flagged"] == 1


def test_null_rows_skipped_and_errors_are_per_symbol():
    def handler(req):
        if "GOOD" in str(req.url):
            return httpx.Response(200, json=_chart([None, 50.0, 51.0], [None, 10, 20]))
        return httpx.Response(503, text="blocked")
    snap = live_market_snapshot(["GOOD", "BAD"], _client(handler), price_move_pct=5.0, volume_multiple=2.0)
    good = next(c for c in snap["companies"] if c["symbol"] == "GOOD")
    bad = next(c for c in snap["companies"] if c["symbol"] == "BAD")
    assert good["state"] == "ok" and good["sessions"] == 2  # the null-close row is dropped
    assert bad["state"] == "error" and "503" in bad["error"]
