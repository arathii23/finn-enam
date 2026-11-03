"""Cold discovery over fictional issuers and a mocked NSE, never company evidence."""
import json
from datetime import datetime

import httpx

from conftest import AR_INDEX, AR_URL, AR_LATE_URL, ANN_APRIL, BASE, TR_URL, make_pdf
from finn.config import PARSER_VERSION
from finn.contracts import ResearchRequest
from finn.discovery import annual_candidate, discover_company_sources
from finn.replay import classify_versions, load_manifest
from finn.retrieval import retrieve_section
from finn.service import App
from finn.sources import documents, nse
from finn.sources.fetch import Fetcher

CUTOFF = "2025-04-30T18:29:59+00:00"


def network(env, index=None, records=None):
    settings, store, _, net = env
    def handler(request):
        url = str(request.url)
        if "annual-reports" in url:
            return httpx.Response(200, json=index if index is not None else AR_INDEX)
        if "corporate-announcements" in url:
            return httpx.Response(200, json=records if records is not None else ANN_APRIL)
        return net(request)
    return Fetcher(store, client=httpx.Client(transport=httpx.MockTransport(handler)), min_interval_s=0)


def company(env, fetcher):
    _, store, _, _ = env
    nse.refresh_security_master(store, fetcher)
    return nse.resolve_company(store, "TESTCO")


def test_cold_discovery_needs_no_manifest_document_urls_and_filters_future_records(env):
    settings, store, _, net = env
    future = {"symbol": "TESTCO", "desc": "Transcript", "attchmntText": "Future call transcript",
              "exchdisstime": "01-May-2025 10:00:00", "attchmntFile": f"{BASE}/future_transcript.pdf"}
    index = {"data": AR_INDEX["data"] + [{"companyName": "Testco Industries Limited", "fromYr": "2024", "toYr": "2025",
             "fileName": AR_LATE_URL, "submission_date": "02-Jun-2025"}]}
    f = network(env, index, ANN_APRIL + [future])
    c = company(env, f)
    assert not store.query("SELECT * FROM document_versions")
    report = discover_company_sources(store, f, settings, c, CUTOFF)
    assert report["state"] == "completed"
    eligible, _ = classify_versions(store, c.company_id, "replay", CUTOFF)
    assert {v["doc_type"] for v in eligible} == {"annual_report", "earnings_call_transcript"}
    assert all(v["availability_status"] == "verified" for v in eligible)
    assert not store.query("SELECT * FROM document_versions WHERE source_url=?", (AR_LATE_URL,))
    assert not any("future_transcript" in u for u in net.calls)
    tr = next(v for v in eligible if v["doc_type"] == "earnings_call_transcript")
    assert tr["period_label"] == "Q4 FY2024-25" and tr["period_start"] is None
    assert tr["identification"]["transcript_dialogue_verified"]
    assert tr["identification"]["management_speakers"] == ["Asha Rao", "Vikram Shah"]
    assert len([q for q in report["queries"] if q["source"] == "announcements"]) <= 4


def test_undated_annual_index_requires_matching_dated_attachment(env):
    settings, store, _, _ = env
    index = {"data": [{k: v for k, v in AR_INDEX["data"][0].items() if k != "submission_date"}]}
    ar_record = {"symbol": "TESTCO", "desc": "Annual Report", "exchdisstime": "03-Jun-2024 15:36:21",
                 "attchmntFile": AR_URL}
    f = network(env, index, ANN_APRIL + [ar_record]); c = company(env, f)
    report = discover_company_sources(store, f, settings, c, CUTOFF)
    assert report["state"] == "completed"
    ar = store.query_one("SELECT * FROM document_versions WHERE doc_type='annual_report'")
    proof = json.loads(ar["availability_evidence"])
    assert proof[0]["method"] == "exchange_announcement" and proof[0]["matched_record"]["attchmntFile"] == AR_URL
    assert ar["published_at"] == "2024-06-03T10:06:21+00:00"


def test_index_company_name_must_match_full_issuer(env):
    _, _, f, _ = env; c = company(env, f)
    res, _ = nse.fetch_annual_report_index(f, c)
    bad = {**AR_INDEX["data"][0], "companyName": "Testco Other Products Limited"}
    assert annual_candidate(bad, res, c) is None


def test_index_date_conflict_is_conservative_and_not_period_end():
    stamp, precision, _ = documents.index_publication({"fromYr": "2023", "toYr": "2024", "period_end_date": "31-Mar-2024",
        "broadcast_dttm": "18-JUL-2024 18:34:53", "disseminationDateTime": "18-JUL-2024 00:00:00"})
    assert stamp == "2024-07-18T18:29:59+00:00" and precision == "date"
    assert documents.index_publication({"period_end_date": "31-Mar-2024"}) == (None, None, None)


def test_period_scope_preserved_without_assuming_fiscal_calendar():
    p = documents.infer_reporting_period(["Q3 FY2025\nConference call transcript", "Q3 & 9MFY25 Earnings Conference Call"], "earnings_call_transcript")
    assert p["period_label"] == "Q3 & 9M FY2024-25" and p["period_scope"] == "quarter and nine months"
    assert "period_start" not in p and "period_end" not in p
    unknown = documents.infer_reporting_period(["Earnings call transcript May 2, 2025"], "earnings_call_transcript")
    assert "period_label" not in unknown


def test_transcript_intimation_cover_is_not_a_transcript_body(env):
    settings, store, _, net = env
    bad_url = f"{BASE}/corporate/transcript_cover_only.pdf"
    net.pdfs[bad_url] = make_pdf(["Testco Industries Limited\nRef: Previous exchange announcement\n"
        "Sub: Transcript of Q4 FY25 earnings call\nDear Sir: Please note that the transcript will be published later."])
    f = network(env); c = company(env, f)
    result = documents.ingest_document(store, f, c, {"url": bad_url, "doc_type": "earnings_call_transcript",
        "_discovered": True, "_published_at": "2025-04-22T10:00:00+00:00", "_precision": "second"})
    assert not result["identification"]["transcript_dialogue_verified"]
    assert not result["identification"]["identity_ok"]
    assert not classify_versions(store, c.company_id, "replay", CUTOFF)[0]


def test_annual_index_period_cannot_override_conflicting_cover(env):
    settings, store, _, net = env
    bad_url = f"{BASE}/corporate/mislabelled_annual.pdf"
    net.pdfs[bad_url] = make_pdf(["Testco Industries Limited\nIntegrated Annual Report 2024-25"])
    f = network(env); c = company(env, f)
    result = documents.ingest_document(store, f, c, {"url": bad_url, "doc_type": "annual_report", "period_label": "FY2023-24",
        "_discovered": True, "_published_at": "2024-06-03T10:00:00+00:00", "_precision": "second"})
    assert result["identification"]["index_period_matches_header"] is False
    assert not result["identification"]["identity_ok"]


def test_revisiting_same_bytes_cannot_erase_verified_publication(env):
    settings, store, _, _ = env
    f = network(env); c = company(env, f)
    first = documents.ingest_document(store, f, c, {"url": AR_URL, "doc_type": "annual_report", "period_label": "FY2023-24",
        "_published_at": "2024-06-03T10:00:00+00:00", "_precision": "second", "_availability_evidence": [{
        "method": "exchange_announcement", "source_url": "https://www.nseindia.com/api/corporate-announcements",
        "matched_record": {"attchmntFile": AR_URL}, "note": "dated source record"}]})
    documents.ingest_document(store, f, c, {"url": AR_URL, "doc_type": "annual_report"})
    saved = store.query_one("SELECT * FROM document_versions WHERE version_id=?", (first["version_id"],))
    assert saved["published_at"] == "2024-06-03T10:00:00+00:00" and json.loads(saved["availability_evidence"])


def test_app_cold_job_discovers_sources_and_reuses_updated_corpus_key(env):
    settings, store, _, _ = env
    f = network(env); company(env, f)
    app = App(settings, store=store, start_worker=False, fetcher_factory=lambda: f)
    req = ResearchRequest(symbol="TESTCO")
    job = app.submit_research(req)
    app.run_job(job["job_id"])
    result = app.job(job["job_id"])
    assert result["state"] == "partial"  # no model key in synthetic test
    assert result["result"]["discovery"]["state"] == "completed"
    assert result["result"]["management_commentary"]["candidate_evidence_ids"]
    assert app.submit_research(req)["job_id"] == job["job_id"]
    assert {"discovering_sources", "downloading_sources"} <= {s["stage"] for s in result["stages"]}


def test_business_retrieval_prefers_operations_over_voting_instructions(env):
    settings, store, _, net = env
    net.pdfs[AR_URL] = make_pdf([
        "Testco Industries Limited\nAnnual Report 2023-24",
        "Company services for shareholders holding stock: log into evoting to inspect your account and annual report. " * 5,
        "Principal business activities: manufacturing pumps and valves. Products and services include water utility equipment "
        "and maintenance services for municipal clients across domestic regions. The business model includes equipment sales and support.",
    ])
    f = network(env); c = company(env, f)
    discover_company_sources(store, f, settings, c, CUTOFF)
    eligible, _ = classify_versions(store, c.company_id, "replay", CUTOFF)
    selected = retrieve_section(store, "business_context", eligible)
    assert selected and "manufacturing pumps" in selected[0]["text"]
    assert not any("evoting" in p["text"] for p in selected)


def test_valid_nse_symbols_with_ampersands_remain_one_query_value(env):
    from datetime import date
    from urllib.parse import parse_qs, urlparse
    query = parse_qs(urlparse(nse.announcements_url("TEST&CO", date(2025, 1, 1), date(2025, 4, 30))).query)
    assert query["symbol"] == ["TEST&CO"] and "CO" not in query
    _, _, f, _ = env; c = company(env, f).model_copy(update={"symbol": "TEST&CO"})
    res, _ = nse.fetch_annual_report_index(f, c)
    assert parse_qs(urlparse(res.url).query)["symbol"] == ["TEST&CO"]


def test_archive_index_entries_do_not_starve_a_newer_agm_annual_pdf(env):
    settings, store, _, net = env
    annual_url = f"{BASE}/corporate/TESTCO_AnnualReport_2023_24.pdf"
    old_pdf_url = f"{BASE}/corporate/TESTCO_annual_2019.pdf"
    numbers = "Assets and liabilities 100 200 300 400 500 600 700 800 900 1000 1100 1200"
    net.pdfs[annual_url] = make_pdf([
        "Testco Industries Limited\nAnnual Report 2023-24",
        "Principal business activities: manufacturing pumps and valves.",
        "Standalone Balance Sheet as at March 31, 2024\n" + numbers,
        "Standalone Statement of Profit and Loss\n" + numbers,
    ] + [f"Corporate governance and financial notes page {i}" for i in range(16)])
    zips = [{"companyName": "Testco Industries Limited", "fromYr": str(year), "toYr": str(year + 1),
             "submission_date": f"03-Jun-{year+1}", "fileName": f"{BASE}/corporate/TESTCO_{year}.zip"}
            for year in (2018, 2019, 2020)]
    index = {"data": zips + [{"companyName": "Testco Industries Limited", "fromYr": "2018", "toYr": "2019",
                              "submission_date": "03-Jun-2019", "fileName": old_pdf_url}]}
    # The subject supplies no annual-report label. The filename is only a cue;
    # exact dated listing and substantive PDF contents must both be verified.
    record = {"symbol": "TESTCO", "desc": "Shareholders meeting", "attchmntText": "Notice of Annual General Meeting",
              "exchdisstime": "31-May-2024 15:36:21", "attchmntFile": annual_url}
    f = network(env, index, ANN_APRIL + [record]); c = company(env, f)
    report = discover_company_sources(store, f, settings, c, CUTOFF)
    assert report["state"] == "completed"
    assert len(report["skipped_candidates"]) == 3
    assert all("No download attempt used" in item["reason"] for item in report["skipped_candidates"])
    assert not any(url.endswith(".zip") or url == old_pdf_url for url in net.calls)
    ar = store.query_one("SELECT * FROM document_versions WHERE doc_type='annual_report'")
    assert ar["source_url"] == annual_url and ar["published_at"] == "2024-05-31T10:06:21+00:00"
    ident = json.loads(ar["identification"])
    assert ident["annual_report_body_verified"] and ident["identity_ok"]
    proof = json.loads(ar["availability_evidence"])[0]
    assert proof["method"] == "exchange_announcement"
    assert proof["matched_record"]["attchmntFile"] == annual_url
    assert len([d for d in report["documents"] if d["doc_type"] == "annual_report"]) == 1
    assert len([q for q in report["queries"] if q["source"] == "announcements"]) <= 4
    assert not store.query("SELECT * FROM model_calls")


def test_filename_only_annual_report_cue_rejects_short_agm_intimation(env):
    settings, store, _, net = env
    url = f"{BASE}/corporate/TESTCO_AnnualReport_AGM.pdf"
    net.pdfs[url] = make_pdf(["Testco Industries Limited\nSub: Annual Report 2023-24 and Annual General Meeting\n"
                              "The annual report will be sent separately. Please note the AGM date."])
    rec = {"symbol": "TESTCO", "desc": "Shareholders meeting", "attchmntText": "AGM intimation",
           "exchdisstime": "31-May-2024 15:36:21", "attchmntFile": url}
    f = network(env, {"data": []}, ANN_APRIL + [rec]); c = company(env, f)
    report = discover_company_sources(store, f, settings, c, CUTOFF)
    assert report["state"] == "partial"
    assert any("lacks substantive financial-statement pages" in issue for issue in report["issues"])
    eligible, _ = classify_versions(store, c.company_id, "replay", CUTOFF)
    assert all(v["doc_type"] != "annual_report" for v in eligible)
    ar = store.query_one("SELECT identification FROM document_versions WHERE source_url=?", (url,))
    assert json.loads(ar["identification"])["annual_report_body_verified"] is False


def test_filename_only_annual_report_cue_rejects_long_nonfinancial_attachment(env):
    settings, store, _, net = env
    url = f"{BASE}/corporate/TESTCO_AnnualReport_BRSR.pdf"
    net.pdfs[url] = make_pdf(["Testco Industries Limited\nAnnual Report 2023-24\nBusiness Responsibility and Sustainability Report"] +
        [f"Sustainability disclosures and environmental initiatives page {i}" for i in range(25)])
    rec = {"symbol": "TESTCO", "desc": "Shareholders meeting", "exchdisstime": "31-May-2024 15:36:21", "attchmntFile": url}
    f = network(env, {"data": []}, ANN_APRIL + [rec]); c = company(env, f)
    report = discover_company_sources(store, f, settings, c, CUTOFF)
    assert report["state"] == "partial"
    eligible, _ = classify_versions(store, c.company_id, "replay", CUTOFF)
    assert all(v["doc_type"] != "annual_report" for v in eligible)


def test_annual_report_filename_does_not_supply_publication_proof(env):
    settings, store, _, net = env
    url = f"{BASE}/corporate/TESTCO_AnnualReport_20240531.pdf"
    undated = {"symbol": "TESTCO", "desc": "Shareholders meeting", "attchmntFile": url}
    f = network(env, {"data": []}, ANN_APRIL + [undated]); c = company(env, f)
    report = discover_company_sources(store, f, settings, c, CUTOFF)
    assert report["state"] == "partial" and url not in net.calls
    assert not store.query("SELECT * FROM document_versions WHERE source_url=?", (url,))


def test_brsr_reference_to_annual_report_is_not_a_complete_annual_report(env):
    settings, store, _, net = env
    url = f"{BASE}/corporate/TESTCO_BRSR.pdf"
    net.pdfs[url] = make_pdf(["Testco Industries Limited\nBusiness Responsibility and Sustainability Report\nForms part of the Annual Report 2023-24"] +
                           [f"Environmental and workforce disclosures for page {i}" for i in range(25)])
    rec = {"symbol": "TESTCO", "desc": "Updates", "attchmntText": "Business Responsibility and Sustainability Report (BRSR), which forms an integral part of the Integrated Annual Report",
           "exchdisstime": "31-May-2024 15:36:21", "attchmntFile": url}
    f = network(env, {"data": []}, ANN_APRIL + [rec]); c = company(env, f)
    report = discover_company_sources(store, f, settings, c, CUTOFF)
    assert report["state"] == "partial"
    assert all(v['doc_type'] != 'annual_report' for v in classify_versions(store, c.company_id, 'replay', CUTOFF)[0])
