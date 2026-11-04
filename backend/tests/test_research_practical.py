"""Regressions for real audit failures: irrelevant answers, dropped conditions and stale sources."""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from finn.api import create_app
from finn.brief import build_source_brief
from finn.contracts import ResearchRequest
from finn.ingest import ingest_replay
from finn.replay import classify_versions, load_manifest
from finn.research import run_research
from finn.service import App
from finn.sources import nse
from finn.sources import documents
from finn.sources.fetch import Fetcher
import httpx


def passage(text, pid="q1", kind="earnings_call_transcript"):
    return {"passage_id": pid, "text": text, "speaker": "Asha Rao" if kind == "earnings_call_transcript" else None,
            "doc_type": kind, "period_label": "FY25", "page_index": 2}


def build(env):
    settings, store, fetcher, net = env
    ingest_replay(store, fetcher, settings, load_manifest(settings.manifest_path), ["TESTCO"], log=lambda s: None)
    return settings, store, net


def test_unrelated_question_is_not_answered_by_generic_growth_sentences():
    result = build_source_brief({"management_commentary": [passage("Revenue increased this year. Margins improved across the business.")]},
                                "What is the auditor resignation reason?")
    assert result.status == "empty" and not result.highlights
    assert "matched" in result.headline


def test_generic_auditor_mention_does_not_answer_a_resignation_question():
    result = build_source_brief({"business_context": [passage("Our auditors reviewed the annual accounts and the financial statements.", kind="annual_report")]},
                                "Why did the auditor resign?")
    # No sentence describes a resignation; generic audit text is not relevant evidence.
    assert not result.highlights


def test_long_acquisition_and_operating_conditions_remain_attached_to_guidance():
    first = "We expect revenue growth of 4.5 to 5 percent in constant currency for the full year, based on the operating plan reviewed by management and the commercial contracts currently in execution."
    condition = "However, this guidance excludes the proposed acquisition and assumes that discretionary client spending recovers during the second half; it remains subject to the completion schedule of a number of large programmes that are still being mobilised."
    source = first + " " + condition
    result = build_source_brief({"management_commentary": [passage(source)]}, "What is the revenue growth guidance?")
    assert result.highlights[0].quote == source
    assert "excludes the proposed acquisition" in result.highlights[0].quote
    assert not result.highlights[0].quote.endswith("…")


def test_oversized_conditional_sentence_abstains_instead_of_truncating():
    source = "Revenue guidance assumes " + "a separately disclosed operating condition, " * 55 + "and excludes acquisitions."
    result = build_source_brief({"management_commentary": [passage(source)]}, "What is the revenue guidance?")
    assert not result.highlights


def test_question_retrieval_does_not_force_business_anchors_or_call_model_without_matches(env):
    settings, store, _ = build(env)
    company = nse.resolve_company(store, "TESTCO")
    state, output = run_research(store, settings, load_manifest(settings.manifest_path), company,
                                 ResearchRequest(symbol="TESTCO", question="Why did the auditor resign?"),
                                 None, None, lambda s: None)
    assert state == "partial" and output.generation.status == "skipped_no_evidence"
    assert not output.evidence_index
    assert any(g.kind == "question" for g in output.evidence_gaps)
    assert not store.query("SELECT * FROM model_calls")


def test_live_mode_still_excludes_unverified_publication_and_future_sources(env):
    settings, store, _ = build(env)
    company = nse.resolve_company(store, "TESTCO")
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    store.execute("UPDATE document_versions SET published_at=? WHERE doc_type='earnings_call_transcript'", (future,))
    eligible, excluded = classify_versions(store, company.company_id, "live", None)
    assert all(v["availability_status"] == "verified" for v in eligible)
    assert not any(v["doc_type"] == "earnings_call_transcript" for v in eligible)
    assert any("source-check cutoff" in " ".join(v["exclusion_reasons"]) for v in excluded)
    assert any("publication availability unverified" in v["exclusion_reasons"] for v in excluded)


def test_current_research_is_explicit_and_get_requests_never_refresh(env):
    settings, store, net = build(env)
    app = App(replace(settings, model_provider="keyless"), store, start_worker=False)
    before = len(net.calls)
    with TestClient(create_app(app)) as client:
        overview = client.get('/api/companies/TESTCO/overview?mode=live').json()
        assert overview['freshness']['latest_publication']
        assert client.get('/api/health').json()['capabilities']['current_source_research']
        req = client.post('/api/research', json={'symbol':'TESTCO','mode':'live','question':'What is the growth outlook?'})
        assert req.status_code == 202
        assert app.job(req.json()['job_id'])['state'] == 'queued'
    assert len(net.calls) == before
    assert not store.query('SELECT * FROM model_calls')


def test_current_seven_day_review_matches_the_exchange_check_calendar(env):
    from finn.config import IST
    settings, store, _ = build(env)
    app=App(settings,store,start_worker=False)
    today=datetime.now(IST).date()
    queue=app.portfolio_queue(mode='live',window='7d')
    assert queue['window']['filing_from']==(today-timedelta(days=6)).isoformat()
    assert queue['window']['filing_to']==today.isoformat()


def test_useful_keyless_briefs_appear_in_saved_research(env):
    settings, store, _ = build(env)
    app = App(replace(settings, model_provider="keyless"), store, start_worker=False)
    job = app.submit_research(ResearchRequest(symbol='TESTCO',question='What is the growth outlook?'))
    app.run_job(job['job_id'])
    saved = app.saved_research()['items']
    assert len(saved) == 1 and saved[0]['kind'] == 'source_brief'
    assert saved[0]['job_id'] == job['job_id']
    assert not store.query('SELECT * FROM model_calls')


def test_selected_filing_is_downloaded_only_after_explicit_job_runs(env):
    settings, store, net = build(env)
    app = App(replace(settings, model_provider="keyless"), store, start_worker=False,
              fetcher_factory=lambda: Fetcher(store, client=httpx.Client(transport=httpx.MockTransport(net)), min_interval_s=0))
    event = store.query_one("SELECT * FROM announcements WHERE category='Outcome of Board Meeting'")
    store.execute("UPDATE announcements SET attachment_version_id=NULL WHERE announcement_id=?", (event['announcement_id'],))
    before = len(net.calls)
    job = app.submit_research(ResearchRequest(symbol='TESTCO',event_id=event['announcement_id']))
    assert len(net.calls) == before
    app.run_job(job['job_id'])
    result = app.job(job['job_id'])['result']
    assert result and result['event_filing']['candidate_evidence_ids']
    assert any(url == event['attachment_url'] for url in net.calls[before:])
    assert not store.query('SELECT * FROM model_calls')
    assert app.submit_research(ResearchRequest(symbol='TESTCO',event_id=event['announcement_id']))['reused']


def test_generic_event_question_reads_the_selected_document(env):
    settings,store,_=build(env)
    event=store.query_one("SELECT * FROM announcements WHERE category='Outcome of Board Meeting'")
    company=nse.resolve_company(store,'TESTCO')
    _,out=run_research(store,settings,load_manifest(settings.manifest_path),company,
                       ResearchRequest(symbol='TESTCO',event_id=event['announcement_id'],
                          question='What does this filing state, and what did management say around it?'),None,None,lambda _:None)
    assert out.event_filing and out.event_filing.candidate_evidence_ids
    assert all(out.evidence_index[pid]['version_id']==event['attachment_version_id'] for pid in out.event_filing.candidate_evidence_ids)


def test_reattached_identical_pdf_retains_earliest_publication_proof(env):
    settings, store, net = build(env)
    company = nse.resolve_company(store, 'TESTCO')
    event = store.query_one("SELECT * FROM announcements WHERE category='Outcome of Board Meeting'")
    old = store.query_one("SELECT * FROM document_versions WHERE version_id=?", (event['attachment_version_id'],))
    assert old['availability_evidence'] != '[]'
    repeated = {**event, 'published_at':'2025-04-29T12:00:00+00:00',
                'raw_json':json.dumps({'symbol':'TESTCO','exchdisstime':'29-Apr-2025 17:30:00','attchmntFile':event['attachment_url']})}
    fetcher=Fetcher(store,client=httpx.Client(transport=httpx.MockTransport(net)),min_interval_s=0)
    documents.link_announcement_attachment(store,fetcher,company,repeated)
    current=store.query_one('SELECT * FROM document_versions WHERE version_id=?',(old['version_id'],))
    assert current['published_at']==old['published_at']
    assert current['availability_evidence']==old['availability_evidence']


def test_wrong_company_filing_is_rejected_before_work_is_queued(env):
    settings, store, _ = build(env)
    app=App(settings,store,start_worker=False)
    event=store.query_one('SELECT announcement_id FROM announcements LIMIT 1')
    with TestClient(create_app(app)) as client:
        response=client.post('/api/research',json={'symbol':'OTHERCO','mode':'live','event_id':event['announcement_id']})
        assert response.status_code==409 and response.json()['detail']['state']=='invalid_event'
    assert not store.query('SELECT * FROM jobs')


def test_topic_need_requires_overlap_or_abstains_when_sources_cannot_answer():
    from finn.retrieval import _topic_need
    terms = ["plans", "lunar", "data", "centre", "underwater", "cables"]
    # Nothing missing: previous behaviour, one matching term suffices.
    assert _topic_need(["dividend", "policy"], []) == 1
    # Several terms exist in no source and only one is findable: abstain.
    assert _topic_need(["lunar", "underwater", "cables", "data"], ["lunar", "underwater", "cables"]) is None
    # Half or more of the question is absent from every source: abstain even if other words are generic.
    assert _topic_need(terms, ["lunar", "underwater", "cables"]) is None
    # Some terms missing but several findable: a lone generic word is not enough.
    assert _topic_need(terms, ["lunar", "underwater"]) == 2
    # A single missing word in a short question does not block an otherwise answerable question.
    assert _topic_need(["dividend", "payout"], ["payout"]) == 1


def test_question_about_a_topic_absent_from_the_sources_names_it_and_shows_no_extracts(env):
    settings, store, _ = build(env)
    company = nse.resolve_company(store, "TESTCO")
    _, output = run_research(store, settings, load_manifest(settings.manifest_path), company,
                             ResearchRequest(symbol="TESTCO",
                                             question="What are the plans for a lunar data centre and underwater cables?"),
                             None, None, lambda s: None)
    assert not output.evidence_index
    assert not (output.source_brief and output.source_brief.highlights)
    named = [g.text for g in output.evidence_gaps if g.kind == "question" and "mention:" in g.text]
    assert named and all(word in named[0] for word in ("lunar", "underwater", "cables"))
    assert not store.query("SELECT * FROM model_calls")


def test_asking_what_management_said_leads_with_management_not_an_annual_report_note():
    ar = passage("Actuarial assumptions include attrition rates and mortality tables used for the valuation of obligations.",
                 pid="ar1", kind="annual_report")
    call = passage("Voluntary attrition declined to 12 percent in the quarter and we expect it to stay in this range.", pid="mc1")
    brief = build_source_brief({"business_context": [ar], "management_commentary": [call]},
                               "What did management say about attrition?")
    assert brief.highlights and brief.highlights[0].kind == "management_commentary"


def test_research_deadline_is_reported_in_plain_language_with_a_retry_hint(env):
    settings, store, _ = build(env)
    app = App(replace(settings, research_deadline_s=0), store=store, start_worker=False)
    job = app.submit_research(ResearchRequest(symbol="TESTCO", question="What is the revenue guidance?"))["job_id"]
    app.run_job(job)
    row = app.job(job)
    assert row["state"] == "failed"
    assert "Retry" in row["error"] and "TimeoutError" not in row["error"]
