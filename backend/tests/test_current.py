"""Current portfolio checks use mocked NSE metadata, never PDFs or a model."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import httpx
import pytest

from finn import current
from finn.ingest import ingest_replay
from finn.replay import load_manifest
from finn.sources import nse
from finn.sources.fetch import Fetcher

NOW = datetime(2026, 11, 4, 0, 0, tzinfo=timezone.utc)


def seed(store, *symbols):
    for i, symbol in enumerate(symbols):
        store.insert("security_master", {
            "symbol": symbol, "legal_name": symbol + " Industries Limited", "series": "EQ",
            "listing_date": None, "isin": f"INE{i:06d}001", "source_url": nse.EQUITY_LIST_URL,
            "source_hash": "test-master", "retrieved_at": NOW.isoformat(),
        }, mode="INSERT OR REPLACE")


def announcement(symbol="TESTCO", **changes):
    return {"symbol": symbol, "desc": "Updates", "attchmntText": "Company disclosure",
            "exchdisstime": "03-Nov-2026 16:00:00",
            "attchmntFile": "https://nsearchives.nseindia.com/corporate/notice.pdf", **changes}


def factory(store, response_for, calls):
    def handler(request):
        calls.append(request)
        assert request.extensions["timeout"]["read"] <= 3
        assert not request.url.path.lower().endswith(".pdf")
        assert "annual-reports" not in str(request.url)
        if request.url.path == "/":
            return httpx.Response(200, text="<html>exchange</html>")
        assert request.url.path == "/api/corporate-announcements"
        response = response_for(request.url.params["symbol"])
        return response if isinstance(response, httpx.Response) else httpx.Response(200, json=response)
    return lambda: Fetcher(store, client=httpx.Client(transport=httpx.MockTransport(handler)), min_interval_s=0)


@pytest.fixture(autouse=True)
def freeze_clock(monkeypatch):
    monkeypatch.setattr(current, "_now", lambda: NOW)


def test_current_metadata_check_preserves_existing_rows_and_partial_failure(env):
    settings, store, _, _ = env
    seed(store, "TESTCO", "OTHERCO")
    company = nse.resolve_company(store, "TESTCO")
    old = announcement(exchdisstime="03-Nov-2025 16:00:00", attchmntFile=None)
    nse.store_announcements(store, company, SimpleNamespace(retrieved_at=NOW.isoformat(),
        url=nse.ANNOUNCEMENTS_API, content_hash="old-hash"), [old])
    calls = []
    make = factory(store, lambda symbol: [announcement()] if symbol == "TESTCO" else httpx.Response(403), calls)
    report = current.refresh_portfolio_sources(store, settings, ["TESTCO", "OTHERCO"], make)
    assert report["state"] == "partial" and report["checked"] == 1
    assert report["from_day"] == "2026-10-29" and report["to_day"] == "2026-11-04"
    assert [(c["state"], c["announcements"]) for c in report["companies"]] == [("fetched", 1), ("error", 0)]
    assert len(store.query("SELECT * FROM announcements")) == 2
    assert current.read_refresh_report(settings) == report
    assert not list(settings.data_dir.glob(".current-refresh-*"))
    assert not store.query("SELECT * FROM model_calls")


def test_empty_valid_response_is_checked_but_does_not_delete_stored_filings(env):
    settings, store, _, _ = env
    seed(store, "TESTCO")
    company = nse.resolve_company(store, "TESTCO")
    nse.store_announcements(store, company, SimpleNamespace(retrieved_at=NOW.isoformat(),
        url=nse.ANNOUNCEMENTS_API, content_hash="old-hash"), [announcement()])
    report = current.refresh_portfolio_sources(store, settings, ["TESTCO"], factory(store, lambda _: [], []))
    assert report["state"] == "completed" and report["checked"] == 1
    assert report["companies"][0]["state"] == "fetched" and report["companies"][0]["announcements"] == 0
    assert len(store.query("SELECT * FROM announcements")) == 1


def test_cache_reuses_report_for_same_days_and_symbol_set_without_network(env):
    settings, store, _, _ = env
    seed(store, "TESTCO", "OTHERCO")
    calls = []
    make = factory(store, lambda _: [], calls)
    first = current.refresh_portfolio_sources(store, settings, ["TESTCO", "OTHERCO"], make)
    count = len(calls)
    second = current.refresh_portfolio_sources(store, settings, ["otherco", "TESTCO", "TESTCO"],
        lambda: pytest.fail("A cached report must not create a fetcher."))
    assert second["cached"] is True and first["cached"] is False
    assert second["started_at"] == first["started_at"] and second["finished_at"] == first["finished_at"]
    assert len(calls) == count
    current.refresh_portfolio_sources(store, settings, ["TESTCO", "OTHERCO"], make, days=1)
    assert len(calls) > count


def test_expired_report_is_rechecked_and_bad_cache_file_does_not_block_check(env):
    settings, store, _, _ = env
    seed(store, "TESTCO")
    calls = []
    make = factory(store, lambda _: [], calls)
    report = current.refresh_portfolio_sources(store, settings, ["TESTCO"], make)
    report["finished_at"] = (NOW - timedelta(minutes=16)).isoformat()
    current.report_path(settings).write_text(json.dumps(report))
    checked = current.refresh_portfolio_sources(store, settings, ["TESTCO"], make)
    assert checked["cached"] is False
    current.report_path(settings).write_text("incomplete JSON")
    assert current.read_refresh_report(settings) is None
    assert current.refresh_portfolio_sources(store, settings, ["TESTCO"], make)["checked"] == 1


def test_recent_yesterday_window_does_not_claim_today_was_checked(env):
    settings, store, _, _ = env
    seed(store, "TESTCO")
    make = factory(store, lambda _: [], [])
    report = current.refresh_portfolio_sources(store, settings, ["TESTCO"], make)
    report["finished_at"] = (NOW - timedelta(minutes=5)).isoformat()
    report["to_day"] = "2026-11-03"
    current.report_path(settings).write_text(json.dumps(report))
    refreshed = current.refresh_portfolio_sources(store, settings, ["TESTCO"], make)
    assert refreshed["cached"] is False and refreshed["to_day"] == "2026-11-04"


@pytest.mark.parametrize("days", [0, 31, -1, 3.5, True, "7"])
def test_invalid_period_is_rejected_before_creating_a_fetcher(env, days):
    settings, store, _, _ = env
    with pytest.raises(ValueError, match="1 to 30"):
        current.refresh_portfolio_sources(store, settings, ["TESTCO"], lambda: pytest.fail("No fetch expected"), days)
    assert current.read_refresh_report(settings) is None


def test_holding_limit_and_unknown_identity_make_no_network_calls(env):
    settings, store, _, _ = env
    with pytest.raises(ValueError, match="at most 15"):
        current.refresh_portfolio_sources(store, settings, [f"CO{i}" for i in range(16)], lambda: pytest.fail("No fetch expected"))
    report = current.refresh_portfolio_sources(store, settings, ["UNKNOWN"], lambda: pytest.fail("No lookup expected"))
    assert report["checked"] == 0 and report["companies"][0]["state"] == "not_checked"
    assert not store.query("SELECT * FROM model_calls")


def test_budget_stops_following_symbols_and_retains_first_success(env, monkeypatch):
    settings, store, _, _ = env
    seed(store, "TESTCO", "OTHERCO", "THIRDCO")
    clock = [0.0]
    monkeypatch.setattr(current, "_clock", lambda: clock[0])
    def response(symbol):
        if symbol == "OTHERCO":
            clock[0] = 46.0
        return [announcement(symbol)]
    calls = []
    report = current.refresh_portfolio_sources(store, settings, ["TESTCO", "OTHERCO", "THIRDCO"], factory(store, response, calls))
    assert report["checked"] == 1 and report["state"] == "partial"
    assert [c["state"] for c in report["companies"]] == ["fetched", "timeout", "timeout"]
    assert len([c for c in calls if "symbol" in c.url.params]) == 2
    assert len(store.query("SELECT * FROM announcements")) == 1


@pytest.mark.parametrize("payload", [{}, {"data": "not-a-list"}, {"error": "blocked"}])
def test_unrecognised_success_body_is_not_an_all_clear(env, payload):
    settings, store, _, _ = env
    seed(store, "TESTCO")
    report = current.refresh_portfolio_sources(store, settings, ["TESTCO"], factory(store, lambda _: payload, []))
    assert report["checked"] == 0 and report["companies"][0]["state"] == "error"
    assert not store.query("SELECT * FROM announcements")


def test_mixed_bad_metadata_cannot_falsely_certify_company_as_checked(env):
    settings, store, _, _ = env
    seed(store, "TESTCO")
    records = [announcement(), announcement("OTHERCO"), announcement(exchdisstime="not-a-date"),
               announcement(exchdisstime="03-Nov-2025 16:00:00"),
               announcement(exchdisstime="04-Nov-2026 23:00:00"),
               announcement(attchmntFile="javascript:alert(1)"), "malformed row"]
    report = current.refresh_portfolio_sources(store, settings, ["TESTCO"], factory(store, lambda _: records, []))
    assert report["checked"] == 0
    entry = report["companies"][0]
    assert entry["state"] == "error" and entry["announcements"] == 1 and "6 source record" in entry["error"]
    assert len(store.query("SELECT * FROM announcements")) == 1
    assert not store.query("SELECT * FROM model_calls")


def test_existing_cached_attachment_is_linked_without_downloading_a_pdf(env):
    settings, store, fetcher, _ = env
    ingest_replay(store, fetcher, settings, load_manifest(settings.manifest_path), ["TESTCO"], log=lambda _: None)
    existing = store.query_one("SELECT * FROM announcements WHERE attachment_version_id IS NOT NULL LIMIT 1")
    assert existing is not None
    calls = []
    record = announcement(attchmntFile=existing["attachment_url"])
    report = current.refresh_portfolio_sources(store, settings, ["TESTCO"], factory(store, lambda _: [record], calls))
    assert report["checked"] == 1
    fresh = store.query_one("SELECT * FROM announcements WHERE published_at LIKE '2026-%'")
    assert fresh["attachment_version_id"] == existing["attachment_version_id"]
    assert fresh["attachment_state"] == "fetched"
    assert all(not request.url.path.endswith(".pdf") for request in calls)
    assert not store.query("SELECT * FROM model_calls")
