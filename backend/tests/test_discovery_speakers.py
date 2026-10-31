"""Fictional short fixtures reflecting inspected HDFC/CERA publisher layouts.

These are parser tests, not company evidence or interviews. Real source observations
remain in data/verification/cold_source_audit_2026_10_31.json.
"""
from finn.sources.documents import chunk_page, transcript_speakers


def test_uppercase_inline_roster_matches_titlecase_dialogue_only():
    pages = [
        "MANAGEMENT: MR. ASHA RAO – MANAGING DIRECTOR\n"
        "AND CHIEF EXECUTIVE OFFICER – TEST BANK\n"
        "MR. VIKRAM SHAH – CHIEF FINANCIAL\nOFFICER – TEST BANK\n"
        "ANALYSTS\nMR. RAVI KUMAR – RESEARCH ANALYST",
        "Moderator: Welcome to this earnings conference call and the opening remarks.\n"
        "Asha Rao: Our business demand remains steady and management expects stable pricing.\n"
        "Ravi Kumar: What is management assuming about new business and pricing?\n"
        "Vikram Shah: Pricing guidance remains conditional on the existing contract terms.",
    ]
    known, management = transcript_speakers(pages)
    assert management == {"Asha Rao", "Vikram Shah"}
    assert "Ravi Kumar" in known and "Ravi Kumar" not in management
    chunks, _ = chunk_page(pages[1], True, None, known)
    assert {speaker for _, speaker in chunks} == {"Moderator", "Asha Rao", "Ravi Kumar", "Vikram Shah"}


def test_prose_management_declaration_excludes_host_and_analysts():
    pages = [
        "Moderator: I now hand the call to Mr. Devrishi Singh of the investor relations host.\n"
        "Devrishi Singh: We have with us today, the management team comprising Mr. Asha Rao\n"
        "- CFO; and Mr. Vikram Shah - VP, Finance and Investor Relations.\n"
        "We will start with brief opening remarks and then open the call for Q&A.\n"
        "Asha Rao: Our revenue outlook depends on the demand environment and distributor orders.\n"
        "Vikram Shah: Our guidance remains subject to the capital project reaching completion.\n"
        "Moderator: The next question is from Mr. Ravi Kumar of the research department.\n"
        "Ravi Kumar: Why does management expect demand to improve next year?",
    ]
    known, management = transcript_speakers(pages)
    assert management == {"Asha Rao", "Vikram Shah"}
    assert {"Devrishi Singh", "Ravi Kumar"}.issubset(known)
    assert not ({"Devrishi Singh", "Ravi Kumar"} & management)


def test_cover_metadata_is_not_treated_as_a_person_or_carried_speaker():
    cover = "Regd. Office: Test Industries House, Mumbai, India, registered correspondence office.\n" \
            "Scrip ID: TESTCO is the identifier used for exchange correspondence.\n" \
            "Scrip Code: TESTCO is provided here for the exchange listing department."
    known, management = transcript_speakers([cover])
    chunks, speaker = chunk_page(cover, True, None, known)
    assert not management and known == {"Moderator"}
    assert chunks and all(s is None for _, s in chunks) and speaker is None


def test_incidental_mentions_do_not_manufacture_a_management_roster():
    pages = ["Management said Mr. Asha Rao - Chief Financial Officer would attend this call.\n"
             "Moderator: Mr. Asha Rao has joined the call, and we will now start questions.\n"
             "Ravi Kumar: I would like management to explain how the business is performing.\n"
             "Asha Rao: Demand remained steady during the quarter and pricing is unchanged."]
    known, management = transcript_speakers(pages)
    assert "Asha Rao" in known and not management
