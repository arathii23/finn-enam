"""Subscription isolation, opt-in, retries and API regression checks."""
from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from finn.api import create_app
from finn.phone_alerts import PhoneAlerts, PhoneError, RedisPhoneStore
from finn.service import App

TOKEN_A, TOKEN_B = "a" * 43, "b" * 43
NOW = datetime.now(timezone.utc)
COMPANIES = [{"symbol": "INFY", "name": "Infosys"}, {"symbol": "HDFCBANK", "name": "HDFC Bank"}]


class MemoryStore:
    """Independent record copies and lock/allowance semantics for service tests."""
    def __init__(self):
        self.rows, self.limits, self.locks = {}, {}, set()
        self.last_status = None

    def get(self, identity):
        return copy.deepcopy(self.rows.get(identity))

    def save(self, identity, record):
        self.rows[identity] = copy.deepcopy(record)

    def all(self):
        return copy.deepcopy(self.rows)

    def delete(self, identity):
        self.rows.pop(identity, None)

    @contextmanager
    def lock(self, identity, seconds=90):
        if identity in self.locks:
            raise PhoneError("busy", 409)
        self.locks.add(identity)
        try:
            yield
        finally:
            self.locks.remove(identity)

    def allowance(self, name, limit, seconds):
        count = self.limits.get(name, 0)
        if count >= limit:
            return False
        self.limits[name] = count + 1
        return True

    def status(self):
        return self.last_status

    def save_status(self, value):
        self.last_status = copy.deepcopy(value)


@pytest.fixture
def phone(monkeypatch):
    store, calls = MemoryStore(), []
    manager = PhoneAlerts(store, COMPANIES, sender=lambda topic, item: calls.append((topic, item)))
    monkeypatch.setattr("finn.phone_alerts.timestamp", lambda: (NOW - timedelta(seconds=20)).isoformat())
    return manager, store, calls


def enable(manager, token=TOKEN_A, symbols=None, groups=None):
    symbols, groups = symbols or ["INFY"], groups or ["results"]
    manager.save(token, symbols, groups, False, "client")
    manager.test(token)
    return manager.save(token, symbols, groups, True, "client")


def candidate(identity, symbol="INFY", category="results", age_seconds=1):
    return {"symbol": symbol, "event": {"announcement_id": identity, "ref_category": category,
            "subject": f"Source headline {identity}", "published_at": (NOW - timedelta(seconds=age_seconds)).isoformat(),
            "attachment_url": f"https://nsearchives.nseindia.com/corporate/{identity}.pdf"}}


def dispatch(manager, events, dry_run=False, checked=None):
    companies = [{"symbol": company["symbol"], "leading_events": [item["event"] for item in events if item["symbol"] == company["symbol"]],
                  "notable_events": []} for company in COMPANIES]
    return manager.dispatch(lambda: {"companies": [{"symbol": s, "state": "fetched"} for s in (checked or ["INFY", "HDFCBANK"])]},
                            lambda: {"companies": companies}, dry_run=dry_run)


def test_separate_topics_credentials_and_idempotent_saves(phone):
    manager, store, _ = phone
    first = manager.save(TOKEN_A, ["INFY"], ["results"], False, "client")
    second = manager.save(TOKEN_B, ["HDFCBANK"], ["business"], False, "client")
    assert first["topic"] != second["topic"]
    assert manager.get(TOKEN_A)["symbols"] == ["INFY"]
    assert manager.save(TOKEN_A, ["HDFCBANK"], ["results"], False, "client")["topic"] == first["topic"]
    assert len(store.rows) == 2 and TOKEN_A not in repr(store.rows)
    assert "sent" not in first and "starts" not in first
    with pytest.raises(PhoneError) as error:
        manager.get("wrong")
    assert error.value.status == 401


def test_test_and_enable_are_separate_explicit_actions(phone):
    manager, _, calls = phone
    manager.save(TOKEN_A, ["INFY"], ["results"], False, "client")
    with pytest.raises(PhoneError, match="confirm"):
        manager.save(TOKEN_A, ["INFY"], ["results"], True, "client")
    assert calls == []
    manager.test(TOKEN_A)
    assert len(calls) == 1 and manager.get(TOKEN_A)["active"] is False
    with pytest.raises(PhoneError) as error:
        manager.test(TOKEN_A)
    assert error.value.status == 429
    manager.save(TOKEN_A, ["INFY"], ["results"], True, "client")
    assert manager.get(TOKEN_A)["active"] is True


def test_filtering_dry_run_and_successful_delivery_deduplicate(phone):
    manager, store, calls = phone
    setup = enable(manager)
    calls.clear()
    events = [candidate("wanted"), candidate("other-company", "HDFCBANK"),
              candidate("other-type", category="dividend"), candidate("old", age_seconds=100)]
    assert dispatch(manager, events, dry_run=True)["matched_devices"] == 1
    assert calls == [] and not store.last_status
    assert dispatch(manager, events)["sent"] == 1 and len(calls) == 1
    assert calls[0][0] == setup["topic"] and "Source headline wanted" in calls[0][1]["body"]
    assert all(text not in calls[0][1]["body"] for text in ["other-company", "other-type", "old"])
    assert dispatch(manager, events)["sent"] == 0 and len(calls) == 1


def test_pause_resume_and_new_follow_skip_backlog(phone, monkeypatch):
    manager, store, calls = phone
    before = (NOW - timedelta(minutes=5)).isoformat()
    monkeypatch.setattr("finn.phone_alerts.timestamp", lambda: before)
    enable(manager)
    monkeypatch.setattr("finn.phone_alerts.timestamp", lambda: NOW.isoformat())
    manager.save(TOKEN_A, ["INFY", "HDFCBANK"], ["results", "business"], True, "client")
    record = store.get(manager.identity(TOKEN_A))
    assert record["starts"]["INFY"] == before and record["starts"]["HDFCBANK"] == NOW.isoformat()
    assert record["group_starts"]["business"] == NOW.isoformat()
    calls.clear()
    assert dispatch(manager, [candidate("newly-followed-old", "HDFCBANK", age_seconds=60)])["sent"] == 0
    manager.save(TOKEN_A, ["INFY"], ["results"], False, "client")
    assert dispatch(manager, [candidate("paused")])["sent"] == 0
    manager.save(TOKEN_A, ["INFY"], ["results"], True, "client")
    assert dispatch(manager, [candidate("paused")])["sent"] == 0 and calls == []


def test_failure_keeps_pending_and_unchecked_company_cannot_send(phone):
    manager, store, calls = phone
    enable(manager)
    def fail(*_):
        raise httpx.ConnectError("offline")
    manager.sender = fail
    assert dispatch(manager, [candidate("retry")])["failed"] == 1
    assert store.get(manager.identity(TOKEN_A))["sent"] == {}
    manager.sender = lambda topic, item: calls.append((topic, item))
    assert dispatch(manager, [candidate("retry")], checked=["HDFCBANK"])["sent"] == 0
    assert dispatch(manager, [candidate("retry")])["sent"] == 1


def test_daily_limit_and_delete_affect_only_owner(phone):
    manager, _, calls = phone
    enable(manager)
    enable(manager, TOKEN_B, ["HDFCBANK"])
    calls.clear()
    for number in range(3):
        assert dispatch(manager, [candidate(f"daily-{number}")])["sent"] == 1
    assert dispatch(manager, [candidate("deferred")])["deferred"] == 1
    manager.delete(TOKEN_A)
    with pytest.raises(PhoneError) as error:
        manager.get(TOKEN_A)
    assert error.value.status == 404
    assert manager.get(TOKEN_B)["active"] is True
    assert dispatch(manager, [candidate("bank", "HDFCBANK")])["sent"] == 1


def test_api_auth_cors_and_private_responses(env, phone):
    settings, store, _, _ = env
    manager, _, calls = phone
    service = App(replace(settings, phone_job_token="job-secret"), store=store, start_worker=False)
    with TestClient(create_app(service, phone_manager=manager)) as client:
        catalog = client.get("/api/phone/catalog").json()
        assert catalog["available"] is True and "topic" not in repr(catalog)
        assert client.get("/api/phone/subscription").status_code == 401
        headers = {"Authorization": f"Bearer {TOKEN_A}", "Origin": "https://arathii23.github.io"}
        result = client.put("/api/phone/subscription", headers=headers, json={"symbols": ["INFY"], "groups": ["results"]})
        assert result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        assert result.headers["access-control-allow-origin"] == "https://arathii23.github.io"
        assert client.put("/api/phone/subscription", headers=headers,
                          json={"symbols": ["UNKNOWN"], "groups": ["results"]}).status_code == 422
        assert client.put("/api/phone/subscription", headers=headers,
                          json={"symbols": ["INFY"], "groups": ["results"], "topic": "victim"}).status_code == 422
        assert client.post("/api/phone/dispatch", headers=headers).status_code == 401
        preflight = client.options("/api/phone/subscription", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "PUT"})
        assert "access-control-allow-origin" not in preflight.headers
        assert client.post("/api/phone/test", headers=headers).json()["accepted"] is True and len(calls) == 1
        assert client.delete("/api/phone/subscription", headers=headers).status_code == 200


def test_missing_storage_is_explicit(env):
    settings, store, _, _ = env
    with TestClient(create_app(App(settings, store=store, start_worker=False), phone_manager=PhoneAlerts(None, COMPANIES))) as client:
        assert client.get("/api/phone/catalog").json()["available"] is False
        assert client.put("/api/phone/subscription", headers={"Authorization": f"Bearer {TOKEN_A}"},
                          json={"symbols": ["INFY"], "groups": ["results"]}).status_code == 503


def test_redis_rest_errors_are_sanitized():
    transport = httpx.MockTransport(lambda request: httpx.Response(429, json={"error": "a-private-topic and private-token"}))
    store = RedisPhoneStore("https://fixture.upstash.io", "private-token", transport=transport)
    with pytest.raises(PhoneError) as error:
        store.command("GET", "finn:phone:v1:status")
    assert "private" not in str(error.value) and "429" not in str(error.value)
    for url in ("https://evil.test", "http://fixture.upstash.io", "https://user:secret@fixture.upstash.io"):
        with pytest.raises(ValueError):
            RedisPhoneStore(url, "token")


def test_shared_free_allowance_defers_without_consuming_pending(phone):
    from finn.phone_alerts import DAILY_BUDGET
    manager, store, calls = phone
    enable(manager)
    calls.clear()
    today = datetime.now(timezone.utc).date().isoformat()
    store.limits['delivery:' + today] = DAILY_BUDGET
    result = dispatch(manager, [candidate('quota')])
    assert result['deferred'] == 1 and calls == []
    assert store.get(manager.identity(TOKEN_A))['sent'] == {}


def test_empty_subscribers_need_no_source_calls_and_scheduler_auth_is_separate(env, phone):
    settings, store, _, _ = env
    manager, _, _ = phone
    def fail():
        pytest.fail('No source refresh is needed without active subscribers')
    service = App(replace(settings, phone_job_token='job-secret'), store=store, start_worker=False)
    service.refresh_current_portfolio = lambda days: fail()
    with TestClient(create_app(service, phone_manager=manager)) as client:
        response = client.post('/api/phone/dispatch', headers={'Authorization': 'Bearer job-secret'})
        assert response.status_code == 200 and response.json()['dry_run'] is True
        assert response.json()['active'] == 0
        assert client.post('/api/phone/dispatch', headers={'Authorization': f'Bearer {TOKEN_A}'}).status_code == 401


def test_invalid_phone_storage_config_preserves_core_application(env):
    settings, store, _, _ = env
    settings = replace(settings, phone_redis_url='https://wrong.example', phone_redis_token='secret', phone_job_token='job')
    with TestClient(create_app(App(settings, store=store, start_worker=False))) as client:
        assert client.get('/api/health').status_code == 200
        assert client.get('/api/phone/catalog').json()['available'] is False


def test_large_unicode_bundles_stay_within_ntfy_text_limit(phone):
    manager, store, calls = phone
    enable(manager)
    calls.clear()
    events = [candidate(f'large-{i}') for i in range(5)]
    for row in events:
        row['event']['subject'] = 'आ' * 240
        row['event']['attachment_url'] += '?source=' + 'x' * 900
    assert dispatch(manager, events)['sent'] == 1
    assert len(calls[0][1]['body'].encode('utf-8')) <= 4000
    record = store.get(manager.identity(TOKEN_A))
    assert 0 < len(record['sent']) < 5
    assert len(record['last_items']) == len(record['sent'])


def test_bundle_opens_a_public_source_on_a_separate_phone(phone):
    manager, _, calls = phone
    enable(manager)
    calls.clear()
    assert dispatch(manager, [candidate('first'), candidate('second')])['sent'] == 1
    message = calls[0][1]
    assert message['click_url'].startswith('https://nsearchives.nseindia.com/corporate/')
    assert '#/alerts' not in message['click_url']
    assert 'first.pdf' in message['body'] and 'second.pdf' in message['body']
