"""Synthetic appointment filings; no live sources, model or spend."""
import pytest
from fastapi.testclient import TestClient

from finn.api import create_app
from finn.management import extract_appointment
from finn.prioritize import classify, TIER_LEADING, TIER_NOTABLE, TIER_ROUTINE
from finn.service import App
from finn.ingest import ingest_replay
from finn.replay import load_manifest

SUBJECT = "Appointment of Ms. Asha Rao as Chief Financial Officer w.e.f. April 8, 2025."
ACTION = "Ms. Asha Rao has been appointed as ‘Chief Financial Officer’ w.e.f. April 8, 2025."
PROFILE = "Brief Profile: Ms Asha Rao has 18 years of experience. She previously led finance at Example Industries."


def packet(action=ACTION, profile=PROFILE):
    return [{"passage_id": "action", "text": action, "page_index": 1},
            {"passage_id": "bio", "text": profile, "page_index": 2}]


def test_every_field_is_verbatim_in_its_own_citation():
    passages = packet()
    result = extract_appointment(SUBJECT, passages)
    assert result["name"] == "Ms. Asha Rao"
    assert result["role"] == "Chief Financial Officer"
    assert result["effective_date_text"] == "April 8, 2025"
    for field in ("name", "role", "effective_date_text"):
        assert result[field] in ACTION
    assert result["profile_quote"] in PROFILE
    assert result["appointment_evidence_id"] == "action" and result["profile_evidence_id"] == "bio"


def test_inclusion_is_not_presented_as_a_new_hire():
    action = "The Board has today i.e. April 8, 2025, approved the inclusion of Ms. Asha Rao – Group Head-Finance as part of the Senior Management of the Bank with immediate effect."
    result = extract_appointment(SUBJECT, packet(action, "Brief Profile of Ms. Asha Rao Ms. Asha Rao joined the Bank in 1999. She has worked in credit."))
    assert result["change"] == "Inclusion in senior management"
    assert result["role"] == "Group Head-Finance"
    assert result["effective_date_text"] == "April 8, 2025"


@pytest.mark.parametrize("action,profile", [
    (ACTION.replace("Asha Rao", "Ritu Singh"), PROFILE),
    (ACTION, PROFILE.replace("Asha Rao", "Ritu Singh")),
    (ACTION.replace(" w.e.f. April 8, 2025", ""), PROFILE),
    ("Ms. Asha Rao has been appointed as CFO w.e.f. a future date. She joined the company effective April 8, 2010.", PROFILE),
    (ACTION, "Ms Asha Rao has 18 years of experience."),
    (ACTION, "Brief Profile: Ms Asha Rao has 18 years of experience but the sentence is truncated"),
    ("Ms. Asha Rao is a Chief Financial Officer. She joined in 2010.", PROFILE),
])
def test_missing_or_mismatched_fields_omit_the_card(action, profile):
    assert extract_appointment(SUBJECT, packet(action, profile)) is None


def test_dividend_and_multiple_candidates_do_not_produce_a_profile():
    assert extract_appointment("Board of Directors recommends a dividend", packet()) is None
    assert extract_appointment(SUBJECT + " Appointment of Mr. Ritu Singh as CEO.", packet()) is None


@pytest.mark.parametrize("category,subject,expected,tier", [
    ("Dividend", "Board of Directors recommended a dividend", "dividend", TIER_NOTABLE),
    ("Record Date", "Record date for dividend approved by directors", "dividend", TIER_NOTABLE),
    ("Updates", "Appointment of Secretarial Auditors", "unclassified", TIER_ROUTINE),
    ("Appointment", "Appointment of M/s. Example & Co., Company Secretaries", "unclassified", TIER_ROUTINE),
    ("Change in Management", "Resignation of statutory auditor", "unclassified", TIER_ROUTINE),
    ("Appointment", SUBJECT, "management_change", TIER_LEADING),
    ("Updates", "Resignation of Chief Financial Officer", "management_change", TIER_LEADING),
    ("Updates", "Board considered and appointed Shri Arun Rao as Whole-time Director", "management_change", TIER_LEADING),
])
def test_classification_requires_a_personnel_change(category, subject, expected, tier):
    result = classify(category, subject)
    assert (result["ref_category"], result["tier"]) == (expected, tier)


def test_endpoint_binds_company_attachment_cutoff_and_review_window(env):
    settings, store, fetcher, _ = env
    ingest_replay(store, fetcher, settings, load_manifest(settings.manifest_path), ["TESTCO"], log=lambda s: None)
    ann = store.query_one("SELECT * FROM announcements WHERE category='Outcome of Board Meeting'")
    vid = ann["attachment_version_id"]
    store.execute("DELETE FROM passages WHERE version_id=?", (vid,))
    for i, p in enumerate(packet()):
        store.execute("INSERT INTO passages (passage_id,version_id,page_index,text,extraction_status,seq) VALUES (?,?,?,?,?,?)",
                      (p["passage_id"], vid, p["page_index"], p["text"], "extracted", i))
    store.execute("UPDATE announcements SET category='Appointment',subject=?,published_at='2025-04-08T10:00:00+00:00' WHERE announcement_id=?", (SUBJECT, ann["announcement_id"]))
    app = App(settings, store, start_worker=False)
    with TestClient(create_app(app)) as client:
        url = "/api/companies/TESTCO/management"
        result = client.get(url).json()
        assert result["served"] == "deterministic" and len(result["items"]) == 1
        assert result["items"][0]["in_review_window"] is False
        assert result["items"][0]["version_id"] == vid
        assert client.get('/api/companies/OTHERCO/management').json()["items"] == []
        assert client.get('/api/companies/NOPE/management').status_code == 404
        assert client.get(url + '?mode=bogus').status_code == 422
        store.execute("UPDATE announcements SET published_at='2025-05-01T10:00:00+00:00' WHERE announcement_id=?", (ann["announcement_id"],))
        assert client.get(url).json()["items"] == []
        store.execute("UPDATE announcements SET published_at='2025-04-08T10:00:00+00:00' WHERE announcement_id=?", (ann["announcement_id"],))
        store.execute("UPDATE document_versions SET published_at='2025-05-01T10:00:00+00:00' WHERE version_id=?", (vid,))
        assert client.get(url).json()["items"] == []
        store.execute("UPDATE document_versions SET published_at='2025-04-08T10:00:00+00:00',availability_status='unverified' WHERE version_id=?", (vid,))
        assert client.get(url).json()["items"] == []
        store.execute("UPDATE document_versions SET availability_status='verified' WHERE version_id=?", (vid,))
        store.execute("UPDATE announcements SET attachment_version_id=NULL WHERE announcement_id=?", (ann["announcement_id"],))
        assert client.get(url).json()["items"] == []
    assert not store.query("SELECT * FROM model_calls")
