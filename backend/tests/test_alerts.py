from datetime import datetime, timezone

import pytest

from finn import alerts
from finn.alerts import (ADVICE_FOOTER, build_notifications, empty_state,
                         pending_notifications, send_pending)


def test_builds_leading_and_owner_selected_messages_only_for_checked_holdings():
    queue = {"companies": [
        {"symbol": "INFY", "leading_events": [{
            "announcement_id": "ann_1", "ref_category": "results", "tier": 1,
            "subject": "Quarterly results", "published_at": "2026-11-17T10:00:00+00:00",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/INFY.pdf",
        }], "notable_events": [{
            "announcement_id": "ann_2", "ref_category": "dividend", "tier": 2,
            "subject": "Dividend", "attachment_url": "https://nsearchives.nseindia.com/corporate/INFY-dividend.pdf",
        }]},
        {"symbol": "HDFCBANK", "leading_events": [{"announcement_id": "ann_3", "ref_category": "results"}]},
    ]}
    messages = build_notifications(queue, {"companies": []}, checked_symbols={"INFY"},
                                   extra_categories={"dividend"})
    assert [m["key"] for m in messages] == ["filing:ann_1", "filing:ann_2"]
    assert "Quarterly results" in messages[0]["body"]
    assert "Exchange filing: https://nsearchives.nseindia.com/corporate/INFY.pdf" in messages[0]["body"]
    assert "#/c/INFY?results=latest" in messages[0]["body"]
    assert messages[0]["click_url"] == messages[0]["filing_url"]
    assert all(ADVICE_FOOTER in m["body"] for m in messages)


def test_rejects_non_nse_attachment_urls_and_keeps_exchange_record_link_if_valid():
    queue = {"companies": [{"symbol": "INFY", "leading_events": [{
        "announcement_id": "ann_safe", "ref_category": "results", "tier": 1,
        "subject": "Results", "attachment_url": "https://example.org/track",
        "source_url": "https://www.nseindia.com/api/corporate-announcements",
    }, {"announcement_id": "ann_bad", "ref_category": "results", "tier": 1,
        "subject": "Bad URL", "attachment_url": "http://nsearchives.nseindia.com/file.pdf"}]}]}
    messages = build_notifications(queue, {"companies": []})
    safe = next(m for m in messages if m["key"] == "filing:ann_safe")
    bad = next(m for m in messages if m["key"] == "filing:ann_bad")
    assert "Exchange record: https://www.nseindia.com/api/corporate-announcements" in safe["body"]
    assert safe["click_url"] == safe["company_url"]
    assert "example.org" not in safe["body"] and "http://nsearchives" not in bad["body"]


def test_eod_message_is_deduped_by_symbol_and_trading_date_and_disclaims_causality():
    prices = {"companies": [{"symbol": "INFY", "state": "ok", "currency": "INR",
                              "latest": {"trading_date": "2026-11-16", "close": 1000},
                              "anomaly": {"trading_date": "2026-11-16", "flagged": True,
                                          "flags": ["price move +5.2%"]}}]}
    candidates = build_notifications({"companies": []}, prices)
    assert candidates[0]["key"] == "eod:INFY:2026-11-16"
    assert "not attributed to any filing" in candidates[0]["body"]
    assert ADVICE_FOOTER in candidates[0]["body"]


def test_only_successful_delivery_is_recorded_and_duplicate_is_not_retried():
    messages = [{"key": "filing:ok", "kind": "filing", "symbol": "INFY", "title": "INFY · Results", "body": "ok"},
                {"key": "filing:fail", "kind": "filing", "symbol": "INFY", "title": "INFY · Results", "body": "fail"}]
    calls = []

    def sender(topic, item):
        calls.append((topic, item["key"]))
        if item["key"].endswith("fail"):
            raise OSError("network")

    state, report = send_pending(messages, empty_state(), topic="private-test-topic", sender=sender,
                                 now=datetime(2026, 11, 17, tzinfo=timezone.utc))
    assert report == {"sent": ["filing:ok"], "failed": [{"key": "filing:fail", "error": "OSError"}],
                      "filing_delay_seconds": []}
    assert pending_notifications(messages, state) == [messages[1]]
    assert calls == [("private-test-topic", "filing:ok"), ("private-test-topic", "filing:fail")]


def test_topic_is_validated_before_any_delivery():
    calls = []
    with pytest.raises(ValueError, match="NTFY_TOPIC"):
        send_pending([], empty_state(), topic="topic/with/path", sender=lambda *_: calls.append(True))
    assert calls == []


def test_pilot_start_time_skips_backlog():
    now = datetime.fromisoformat("2026-11-17T10:30:00+00:00")
    start = alerts.parse_start_at("2026-11-17T15:30:00+05:30")
    prior = {"announcement_id": "ann_prior", "published_at": "2026-11-17T09:59:59+00:00"}
    new = {"announcement_id": "ann_new", "published_at": "2026-11-17T10:00:01+00:00"}
    queue = {"companies": [{"symbol": "INFY", "leading_events": [prior, new]}]}
    assert [m["key"] for m in build_notifications(queue, {}, now=now, since=start)] == ["filing:ann_new"]
    with pytest.raises(ValueError, match="offset"):
        alerts.parse_start_at("2026-11-17T15:30:00")


def test_nse_mirrors_share_an_alert_identity_across_runs():
    event = {"announcement_id": "ann_com", "attachment_url": "https://nsearchives.nseindia.com/corporate/notice.pdf"}
    mirror = {"announcement_id": "ann_in", "attachment_url": "https://nsearchives.nseindia.in/corporate/notice.pdf"}
    queue = {"companies": [{"symbol": "INFY", "leading_events": [event, mirror]}]}
    candidates = build_notifications(queue, {})
    calls = []
    state, outcome = send_pending(candidates, empty_state(), topic="fixture-topic",
                                  sender=lambda topic, item: calls.append(item["key"]))
    assert calls == ["filing:ann_com"]
    assert outcome["failed"] == []
    assert pending_notifications([candidates[1]], state) == []


def test_cli_phone_test_sends_one_message_without_opening_store(monkeypatch, capsys):
    from finn import cli
    from finn.service import App

    calls = []
    monkeypatch.setenv("NTFY_TOPIC", "fixture-topic")
    monkeypatch.setattr(App, "__init__", lambda *_a, **_kw: pytest.fail("test needs no portfolio store"))
    monkeypatch.setattr(alerts, "_send_ntfy", lambda topic, item: calls.append((topic, item)))
    assert cli.main(["alerts", "--test"]) == 0
    assert len(calls) == 1
    assert calls[0][1]["title"] == "FINN · Test alert"
    assert calls[0][1]["company_url"] == alerts.DEFAULT_SITE_URL
    output = capsys.readouterr().out
    assert "accepted one test" in output and "fixture-topic" not in output
