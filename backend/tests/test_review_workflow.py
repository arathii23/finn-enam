"""Source-backed window, saved-result and all-filings interactions; no network/spend."""
import json

from fastapi.testclient import TestClient

from finn.api import create_app
from finn.ingest import ingest_replay
from finn.replay import load_manifest
from finn.service import App


def build(env):
    settings, store, fetcher, _ = env
    ingest_replay(store, fetcher, settings, load_manifest(settings.manifest_path), ["TESTCO"], log=lambda s: None)
    app = App(settings, store, start_worker=False)
    app.portfolio = {"symbols": ["TESTCO"]}
    return app, store


def test_default_is_last_24_hours_of_labelled_replay(env):
    app, store = build(env)
    result = app.portfolio_queue()
    assert result["window"]["filing_from"] == "2025-04-30"
    assert result["window"]["filing_to"] == "2025-04-30"
    assert result["window"]["stored_only"] is True
    assert result["companies"][0]["coverage"]["announcements"] == 0
    assert not store.query('SELECT * FROM model_calls')


def test_chosen_dates_filter_announcements_and_do_not_use_future_prices(env):
    app, _ = build(env)
    all_rows = app.portfolio_queue(window="all")["companies"][0]
    chosen = app.portfolio_queue(window="custom", filing_from="2025-04-17", filing_to="2025-04-17")["companies"][0]
    assert all_rows["coverage"]["announcements"] == 2
    assert chosen["coverage"]["announcements"] == 1
    assert chosen["leading_events"][0]["category"] == "Outcome of Board Meeting"
    assert chosen["eod_anomaly"]["trading_date"] == "2025-04-17"


def test_actual_routine_records_are_accessible_and_dates_rejected(env):
    app, store = build(env)
    record = store.query_one("SELECT * FROM announcements LIMIT 1")
    record.update(announcement_id="routine", source_key="routine", category="Trading Window", subject="Trading window closure", attachment_version_id=None)
    store.insert("announcements", record)
    with TestClient(create_app(app)) as client:
        company = client.get('/api/portfolio?window=all').json()["companies"][0]
        assert company["routine_count"] == 1
        assert company["routine_events"][0]["announcement_id"] == "routine"
        for query in ['window=custom&filing_from=2025-05-01&filing_to=2025-05-02',
                      'window=custom&filing_from=2025-04-20&filing_to=2025-04-19',
                      'window=custom&filing_from=bad&filing_to=bad', 'window=custom', 'window=bogus']:
            assert client.get('/api/portfolio?' + query).status_code == 422


def test_saved_research_discovery_is_read_only_and_excludes_unfinished_prose(env):
    app, store = build(env)
    company = app.company('TESTCO')
    result = {"company": company, "mode": "replay", "question": "What is management watching?", "event": None,
              "generated_at": "2026-10-31T00:00:00+00:00", "eligible_version_ids": ['synthetic-v1'],
              "generation": {"status": "generated"}}
    for jid, status in [('saved', 'generated'), ('passages-only', 'model_unavailable')]:
        store.insert('jobs', {"job_id": jid, "kind": "research", "idempotency_key": jid, "state": "completed",
                             "stage": None, "stages": "[]", "request": '{}',
                             "result": json.dumps({**result, "generation": {"status": status}}), "error": None,
                             "created_at": result['generated_at'], "updated_at": result['generated_at']})
    with TestClient(create_app(app)) as client:
        saved = client.get('/api/research/saved?symbol=testco').json()['items']
        assert len(saved) == 1 and saved[0]['job_id'] == 'saved'
        assert saved[0]['question'] == result['question'] and saved[0]['document_count'] == 1
        assert client.get('/api/research/saved?symbol=OTHERCO').json()['items'] == []
        assert client.get('/api/research/saved').status_code == 200
    assert len(store.query('SELECT * FROM jobs')) == 2
    assert not store.query('SELECT * FROM model_calls')
