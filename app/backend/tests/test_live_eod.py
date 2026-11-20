"""Live EOD via Yahoo's free chart API — parsing, prev-close chaining and anomaly flagging.

Mocked transport: no network. Confirms live rows are normalised correctly, prev_close is
chained, the deterministic anomaly rule fires, and provider failures degrade to a per-symbol
error rather than raising.
"""
import json
import importlib.util
from pathlib import Path

import httpx
import pytest

from finn.sources.live_eod import _chart_rows, fetch_live_eod, live_market_snapshot


_script_spec = importlib.util.spec_from_file_location(
    "finn_scheduled_prices", Path(__file__).resolve().parents[2] / "scripts" / "refresh_live_prices.py")
scheduled_prices = importlib.util.module_from_spec(_script_spec)
_script_spec.loader.exec_module(scheduled_prices)


def _scheduled_fetch(monkeypatch, payload):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr(scheduled_prices.urllib.request, "urlopen", lambda *_a, **_kw: Response())
    return scheduled_prices._fetch("TEST")


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


def test_missing_ohlc_and_short_parallel_arrays_preserve_valid_daily_closes(monkeypatch):
    payload = _chart([100, 102, 104], [700])
    quote = payload["chart"]["result"][0]["indicators"]["quote"][0]
    for name in ("open", "high", "low"):
        del quote[name]
    fetched = fetch_live_eod("TEST", _client(lambda _: httpx.Response(200, json=payload)))
    assert fetched["state"] == "ok"
    rows = fetched["rows"]
    assert [r["close"] for r in rows] == [100, 102, 104]
    assert [r["prev_close"] for r in rows] == [None, 100, 102]
    assert [r["volume"] for r in rows] == [700, None, None]
    assert all(r[name] is None for r in rows for name in ("open", "high", "low"))
    assert _scheduled_fetch(monkeypatch, payload)["rows"] == rows


def test_provider_dates_survive_out_of_order_and_duplicate_session_bars():
    start = 1_700_000_000
    stamps = [start + 2 * 86400, start, start + 86400, start + 86400 + 3600, None, 10**100]
    quote = {"close": [130, 100, 110, 112, 999, 999], "volume": [30, 10, 20, 22, 1, 1]}
    rows = _chart_rows(stamps, quote)
    assert [r["close"] for r in rows] == [100, 112, 130]
    assert [r["prev_close"] for r in rows] == [None, 100, 112]
    assert [r["source_timestamp"] for r in rows] == [start, start + 86400 + 3600, start + 2 * 86400]
    assert [r["trading_date"] for r in rows] == ["2023-11-15", "2023-11-16", "2023-11-17"]
    assert scheduled_prices._chart_rows(stamps, quote) == rows


def test_invalid_financial_values_are_omitted_without_inventing_replacements():
    closes = [100, None, True, -1, 0, "106", float("nan"), float("inf"), 108]
    stamps = [1_700_000_000 + i * 86400 for i in range(len(closes))]
    quote = {"close": closes, "volume": [-3] + [400] * 7 + [float("nan")],
             "open": [False] + [None] * 7 + [float("inf")]}
    rows = _chart_rows(stamps, quote)
    assert [r["close"] for r in rows] == [100, 108]
    # A missing/invalid provider session breaks the daily-return chain. The
    # latest close remains useful, without presenting an eight-session move as 1d.
    assert [r["prev_close"] for r in rows] == [None, None]
    assert all(r["volume"] is None and r["open"] is None for r in rows)
    assert scheduled_prices._chart_rows(stamps, quote) == rows


@pytest.mark.parametrize("payload", [
    {"chart": []},
    {"chart": {"result": []}},
    {"chart": {"result": [{"meta": {}, "timestamp": "not-an-array", "indicators": {"quote": [{}]}}]}},
    {"chart": {"result": [{"meta": {}, "timestamp": [1700000000], "indicators": {"quote": [None]}}]}},
])
def test_malformed_chart_is_a_per_symbol_error_in_backend_and_scheduler(monkeypatch, payload):
    result = fetch_live_eod("TEST", _client(lambda _: httpx.Response(200, json=payload)))
    scheduled = _scheduled_fetch(monkeypatch, payload)
    assert result["state"] == scheduled["state"] == "error"
    assert result["error"] == scheduled["error"] == "unexpected Yahoo response shape"


def test_missing_close_is_reported_as_unavailable_not_a_zero_price(monkeypatch):
    payload = _chart([None, None], [100, 100])
    fetched = fetch_live_eod("TEST", _client(lambda _: httpx.Response(200, json=payload)))
    assert fetched["state"] == "error" and "no valid price sessions" in fetched["error"]
    assert _scheduled_fetch(monkeypatch, payload)["state"] == "error"


def test_one_malformed_symbol_does_not_erase_other_portfolio_prices():
    def handler(req):
        payload = _chart([100, 101], [100, 100]) if "GOOD" in str(req.url) else {"chart": []}
        return httpx.Response(200, json=payload)
    snap = live_market_snapshot(["BAD", "GOOD"], _client(handler), price_move_pct=5, volume_multiple=2)
    assert snap["summary"]["ok"] == 1 and snap["summary"]["companies"] == 2
    good = next(c for c in snap["companies"] if c["symbol"] == "GOOD")
    assert good["latest"]["close"] == 101
    assert good["latest"]["trading_date"] == "2023-11-16"


def test_scheduler_handles_invalid_json_as_an_unavailable_symbol(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b"not a JSON response"

    monkeypatch.setattr(scheduled_prices.urllib.request, "urlopen", lambda *_a, **_kw: Response())
    result = scheduled_prices._fetch("TEST")
    assert result["state"] == "error" and result["error"] == "invalid Yahoo JSON response"
