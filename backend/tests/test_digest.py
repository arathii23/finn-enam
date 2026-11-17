from datetime import datetime, timedelta, timezone

import pytest

from finn.digest import build_digest, read_digest, validate_digest, write_atomic

NOW = datetime(2026, 11, 17, tzinfo=timezone.utc)


def queue(*, subject="Rating downgrade", fail=False, attachment="https://nsearchives.nseindia.in/corporate/one.pdf"):
    checked = (NOW - timedelta(minutes=1)).isoformat()
    event = {"announcement_id": "ann_one", "published_at": checked, "subject": subject,
             "attachment_url": attachment, "category": "Credit Rating", "ref_category": "credit_rating",
             "reason": "Material exchange filing", "tier": 1}
    return {
        "companies": [{"symbol": "INFY", "freshness": {"state": "timeout" if fail else "fetched",
                       "last_checked": None if fail else checked}, "leading_events": [] if fail else [event]}],
        "refresh": {"finished_at": checked}, "summary": {},
        "window": {"filing_from": "2026-11-11", "filing_to": "2026-11-17"},
    }


def test_digest_uses_only_subject_and_preserves_base_tier():
    digest = build_digest(queue(), now=NOW)
    item = digest["items"][0]
    assert item["headline"] == item["subject"] == "Rating downgrade"
    assert item["tier"] == item["base_tier"] == 1
    assert item["facts"] == [] and item["extraction"]["state"] == "skipped"


def test_failed_check_carries_forward_and_new_metadata_versions_stay_distinct():
    original = build_digest(queue(), now=NOW)
    partial = build_digest(queue(fail=True), previous=original, now=NOW + timedelta(hours=1))
    assert partial["items"] == original["items"]
    assert partial["checks"]["holdings_checked"] == 0
    modified = build_digest(queue(subject="Revised rating notice"), previous=original, now=NOW + timedelta(hours=2))
    assert modified["items"][0]["version"] != original["items"][0]["version"]
    assert modified["items"][0]["updated"]


def test_non_exchange_attachment_is_omitted_and_tampered_digest_is_rejected(tmp_path):
    digest = build_digest(queue(attachment="https://example.com/filing.pdf"), now=NOW)
    assert digest["items"][0]["source"] is None
    dst = tmp_path / "digest.json"
    write_atomic(dst, digest)
    assert read_digest(dst, NOW) == digest
    digest["items"][0]["tier"] = 3
    with pytest.raises(ValueError, match="fallback"):
        validate_digest(digest, NOW)
