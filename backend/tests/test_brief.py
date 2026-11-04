"""The keyless extractive brief must quote verbatim, never invent, and stay query-aware."""
from finn.brief import build_source_brief


def _mc(text, speaker="Salil Parekh", pid="p_mc", period="Q4 FY25"):
    return {"passage_id": pid, "text": text, "speaker": speaker, "doc_type": "earnings_call_transcript",
            "period_label": period, "page_index": 3}


def _bc(text, pid="p_bc", period="FY25"):
    return {"passage_id": pid, "text": text, "speaker": None, "doc_type": "annual_report",
            "period_label": period, "page_index": 12}


def test_quotes_are_verbatim_substrings_of_source():
    bc_text = ("The Company is a leading IT services provider. Our principal business is digital "
               "transformation across financial services and retail clients.")
    mc_text = ("We expect revenue growth of 1 to 3 percent in constant currency for the year, subject to "
               "discretionary demand. Margins remained resilient.")
    brief = build_source_brief({"business_context": [_bc(bc_text)], "management_commentary": [_mc(mc_text)]},
                               question="What is the revenue growth guidance?")
    assert brief.status == "extractive"
    assert brief.highlights
    for h in brief.highlights:
        # Every quoted fragment (minus any trailing ellipsis) is present verbatim in the source.
        src = bc_text if h.kind == "business_context" else mc_text
        assert h.quote.rstrip("…").strip() in src
    mc = next(h for h in brief.highlights if h.kind == "management_commentary")
    assert mc.speaker == "Salil Parekh"
    # Query about guidance should surface the guidance sentence, with its caveat retained.
    assert "1 to 3 percent" in mc.quote and "subject to" in mc.quote


def test_query_terms_steer_selection():
    mc_text = ("Order pipeline was strong across geographies. Attrition fell to a two-year low this quarter.")
    pick_attr = build_source_brief({"management_commentary": [_mc(mc_text)]}, "what happened to attrition?")
    assert "Attrition" in pick_attr.highlights[0].quote
    pick_pipe = build_source_brief({"management_commentary": [_mc(mc_text)]}, "how is the deal pipeline?")
    assert "pipeline" in pick_pipe.highlights[0].quote.lower()


def test_empty_when_no_passages():
    brief = build_source_brief({"business_context": [], "management_commentary": []}, "anything")
    assert brief.status == "empty"
    assert not brief.highlights


def test_suggestions_gated_by_available_evidence():
    brief = build_source_brief({"business_context": [_bc("Our principal business is cement manufacturing.")]},
                               question=None)
    # No transcript -> no guidance/demand suggestion; business suggestion is offered.
    assert any("segments" in q for q in brief.suggested_questions)
    assert not any("guidance" in q for q in brief.suggested_questions)


def test_guidance_question_surfaces_direct_answer_before_dense_historical_results():
    actual = _mc("Revenue growth was below our expectations. Operating margin was 18 percent.", pid="actual")
    target = _mc("Revenue growth guidance is 1 to 2 percent in constant currency. "
                 "Operating margin guidance is 20 to 22 percent for the year.", pid="target")
    assumptions = _mc("Operating margin guidance is 20 to 22 percent. "
                      "Compensation increases and revenue seasonality are headwinds. "
                      "These headwinds will be partly offset by our cost programme.", pid="assumptions")
    historical = {**_bc("Revenue growth and operating margin for last year are reported below.", pid="historical"),
                  "doc_type": "exchange_filing"}
    brief = build_source_brief({"management_commentary": [actual, target, assumptions],
                               "event_filing": [historical]},
                              "What revenue growth and operating margin guidance does management give?")
    assert brief.highlights[0].evidence_id == "target"
    assert "1 to 2 percent" in brief.highlights[0].quote
    condition = next(h for h in brief.highlights if h.evidence_id == "assumptions")
    assert "partly offset" in condition.quote
    assert all(h.kind == "management_commentary" for h in brief.highlights[:3])


def test_repeated_bundled_guidance_keeps_distinct_assumptions_and_changed_figures():
    def passage(pid, text):
        return {**_mc(text, pid=pid), "version_id": "bundle"}
    first = passage("media", "Our revenue growth guidance is 1 to 2 percent. Operating margin guidance remains 20 to 22 percent.")
    repeat = passage("analyst", "Our revenue growth guidance is 1 to 2 percent. Our operating margin guidance remains 20 to 22 percent.")
    conditions = passage("basis", "Our revenue growth guidance is 1 to 2 percent, assuming demand recovers. "
                                  "Our operating margin guidance remains 20 to 22 percent.")
    changed = passage("changed", "Our revenue growth guidance is 2 to 3 percent. Operating margin guidance remains 20 to 22 percent.")
    brief = build_source_brief({"management_commentary": [first, repeat, conditions, changed]},
                               "What is the revenue growth guidance?")
    ids = {h.evidence_id for h in brief.highlights}
    assert {"media", "basis", "changed"} == ids
    assert next(h.quote for h in brief.highlights if h.evidence_id == "basis") in conditions["text"]
