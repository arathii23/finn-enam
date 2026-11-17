from datetime import datetime, timezone

import pytest

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
    assert "#/c/INFY?mode=live" in messages[0]["body"]
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
    assert "Exchange filing: https://www.nseindia.com/api/corporate-announcements" in safe["body"]
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
