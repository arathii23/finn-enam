"""Tests for the deterministic Numbers-vs-Narrative comparison engine.

These use synthetic passages (no DB, no model) and assert the two things that matter:
a verdict appears only when the comparability gate passes, and the arithmetic is exact.
"""
from finn.compare import build_narrative_numbers, extract_statements, fy_label

MGMT = {"Salil Parekh", "Jayesh Sanghrajka"}


def P(pid, text, doc_type="earnings_call_transcript", period="Q3 FY2024-25",
      speaker="Salil Parekh", pub="2025-01-16T00:00:00+00:00", page=1):
    return {"passage_id": pid, "doc_type": doc_type, "period_label": period, "page_index": page,
            "speaker": speaker, "text": text, "published_at": pub}


def build(passages):
    return build_narrative_numbers("TEST", "Test Ltd", passages, "30 Apr 2025, 23:59 IST",
                                   cutoff_end_year=2025, management=MGMT)


def find(res, metric_key, fy):
    return next((i for i in res["items"] if i["metric_key"] == metric_key and i["fiscal_year"] == fy), None)


def test_fy_label():
    assert fy_label(2025) == "FY2024-25"
    assert fy_label(2026) == "FY2025-26"


def test_below_range_with_exact_delta_and_constant_currency():
    res = build([
        P("g1", "We are revising our FY'25 revenue growth guidance to 4.5% to 5% in constant currency terms."),
        P("o1", "In financial year 2025 our revenues grew at 4.2% in constant currency terms.",
          period="Q4 FY2024-25", speaker="Jayesh Sanghrajka", pub="2025-04-17T00:00:00+00:00"),
    ])
    it = find(res, "revenue_growth", "FY2024-25")
    assert it and it["comparable"] is True
    assert it["basis"] == "constant currency"
    assert it["verdict"]["kind"] == "below_range"
    assert it["verdict"]["delta_pp"] == -0.3            # 4.2 - 4.5, exact
    assert it["guidance"]["evidence_id"] == "g1"
    assert it["outcome"]["evidence_id"] == "o1"


def test_within_range_operating_margin():
    res = build([
        P("g1", "Our operating margin guidance for FY'25 remains unchanged at 20% to 22%."),
        P("o1", "We ended financial year 2025 with an operating margin of 21.1%.",
          period="Q4 FY2024-25", pub="2025-04-17T00:00:00+00:00"),
    ])
    it = find(res, "operating_margin", "FY2024-25")
    assert it and it["verdict"]["kind"] == "within_range" and it["verdict"]["delta_pp"] == 0.0


def test_above_range_delta():
    res = build([
        P("g1", "Our FY'25 revenue growth guidance is 3% to 4% in constant currency terms."),
        P("o1", "In financial year 2025 revenues grew 5.5% in constant currency terms.",
          period="Q4 FY2024-25", pub="2025-04-17T00:00:00+00:00"),
    ])
    it = find(res, "revenue_growth", "FY2024-25")
    assert it["verdict"]["kind"] == "above_range" and it["verdict"]["delta_pp"] == 1.5


def test_outcome_pending_for_future_year_shows_no_verdict():
    res = build([P("g1", "Our guidance for growth in financial year 2026 is 0% to 3% in constant currency terms.",
                   period="Q4 FY2024-25", pub="2025-04-17T00:00:00+00:00")])
    it = find(res, "revenue_growth", "FY2025-26")
    assert it and it["outcome"] is None and it["verdict"]["kind"] == "pending"
    assert it["comparable"] is False


def test_cross_basis_is_not_comparable():
    # Guided in constant currency, but only a reported-currency outcome exists.
    res = build([
        P("g1", "Our FY'25 revenue growth guidance is 4% to 5% in constant currency terms."),
        P("o1", "In financial year 2025 revenues grew 7% in rupee terms.",
          period="Q4 FY2024-25", pub="2025-04-17T00:00:00+00:00"),
    ])
    it = find(res, "revenue_growth", "FY2024-25")
    assert it["comparable"] is False
    assert it["verdict"]["kind"] == "not_comparable"
    assert it["gate_reasons"] and "basis" in it["gate_reasons"][0].lower()


def test_segment_mix_percentage_is_not_a_growth_rate():
    res = build([P("m1", "Our Faucetware segment contributed 37% to our revenues in financial year 2025.",
                   period="Q4 FY2024-25")])
    assert find(res, "revenue_growth", "FY2024-25") is None


def test_quarterly_figure_excluded():
    sts = extract_statements([P("q1", "Revenue grew 6.1% year-on-year in constant currency in Q3 FY25.")], MGMT)
    assert sts == []


def test_analyst_speaker_is_not_treated_as_guidance():
    sts = extract_statements([
        P("a1", "Your FY'25 revenue growth guidance of 4.5% to 5% looks aggressive.", speaker="Some Analyst"),
    ], MGMT)
    assert sts == []


def test_eps_growth_is_disqualified():
    res = build([P("e1", "Basic EPS growth for financial year 2025 was 1.8%.", period="Q4 FY2024-25")])
    assert res["items"] == []
    assert res["empty_reason"]


def test_acquisition_caveat_only_with_explicit_inorganic_language():
    with_signal = build([
        P("g1", "Our FY'25 revenue growth guidance is 4.5% to 5% in constant currency terms."),
        P("o1", "In financial year 2025 revenues grew 4.2% in constant currency terms.",
          period="Q4 FY2024-25", pub="2025-04-17T00:00:00+00:00"),
        P("c1", "Jayesh Sanghrajka: in-tech contributed to inorganic growth this year.",
          speaker="Jayesh Sanghrajka"),
    ])
    it = find(with_signal, "revenue_growth", "FY2024-25")
    assert any("inorganic" in c["text"].lower() and c["evidence_ids"] == ["c1"] for c in it["caveats"])

    without_signal = build([
        P("g1", "Our FY'25 revenue growth guidance is 4.5% to 5% in constant currency terms."),
        P("o1", "In financial year 2025 revenues grew 4.2% in constant currency terms.",
          period="Q4 FY2024-25", pub="2025-04-17T00:00:00+00:00"),
    ])
    it2 = find(without_signal, "revenue_growth", "FY2024-25")
    assert all("inorganic" not in c["text"].lower() for c in it2["caveats"])


def test_empty_management_roster_fails_closed():
    assert extract_statements([P("a", "Our FY25 revenue growth guidance is 3% to 4%.", speaker="Analyst")], set()) == []


def test_explicit_entity_mismatch_and_unknown_vs_explicit_are_not_compared():
    for prefix in ("standalone ", ""):
        result = build([P("g", f"Our {prefix}operating margin guidance for FY25 is 20% to 22%."),
                        P("o", "Our consolidated operating margin for financial year 2025 was 21%.", pub="2025-04-17T00:00:00+00:00")])
        item = find(result, "operating_margin", "FY2024-25")
        assert item and not item["comparable"] and item["verdict"]["kind"] == "not_comparable"


def test_unqualified_issuer_statements_expose_scope_limit():
    result = build([P("g", "Our operating margin guidance for FY25 is 20% to 22%."),
                    P("o", "Our operating margin for financial year 2025 was 21%.", pub="2025-04-17T00:00:00+00:00")])
    item = find(result, "operating_margin", "FY2024-25")
    assert item["entity"] == "not stated" and item["guidance"]["entity"] == "not stated"
    assert any("not independently established" in c["text"] for c in item["caveats"])


def test_a_delivered_outcome_must_be_published_later_than_guidance():
    result = build([P("g", "Our operating margin guidance for FY25 is 20% to 22%."),
                    P("o", "Our operating margin for financial year 2025 was 21%.", pub="2024-12-01T00:00:00+00:00")])
    item = find(result, "operating_margin", "FY2024-25")
    assert item and not item["comparable"] and "publication" in item["verdict"]["summary"].lower()


def test_negative_growth_sign_is_preserved():
    for sign in ("-", "−"):
        result = build([P("g", "Our FY25 revenue growth guidance is 3% to 4% in constant currency terms."),
                        P("o", f"Our revenue growth for financial year 2025 was {sign}2% in constant currency terms.", pub="2025-04-17T00:00:00+00:00")])
        item = find(result, "revenue_growth", "FY2024-25")
        assert item["outcome"]["low"] == -2 and item["outcome"]["value_text"] == sign + "2%"
        assert item["verdict"]["delta_pp"] == -5


def test_explicit_segment_scope_and_ambiguous_years_are_omitted():
    assert not extract_statements([P("s", "Our financial services segment revenue growth guidance for FY25 is 4% to 5%.")], MGMT)
    assert not extract_statements([P("y", "Our FY25 revenue growth was 5% compared to FY24 revenue growth of 3%.")], MGMT)


def test_reported_inr_usd_and_known_unknown_currency_do_not_compare():
    for guided_currency in (" in rupee terms", ""):
        result = build([P("g", f"Our FY25 revenue growth guidance is 3% to 4%{guided_currency}."),
                        P("o", "Our revenue growth for financial year 2025 was 5% in US dollar terms.", pub="2025-04-17T00:00:00+00:00")])
        item = find(result, "revenue_growth", "FY2024-25")
        assert not item["comparable"] and item["verdict"]["kind"] == "not_comparable"
        assert item["outcome"]["reporting_currency"] == "USD"


def test_matching_reported_currency_retains_label_and_unspecified_pairs_have_caveat():
    for suffix, expected in ((" in rupee terms", "INR"), ("", "not stated")):
        result = build([P("g", f"Our FY25 revenue growth guidance is 3% to 4%{suffix}."),
                        P("o", f"Our revenue growth for financial year 2025 was 5%{suffix}.", pub="2025-04-17T00:00:00+00:00")])
        item = find(result, "revenue_growth", "FY2024-25")
        assert item["comparable"] and item["reporting_currency"] == expected
        if expected == "not stated":
            assert any("currency equality" in c["text"] for c in item["caveats"])


def test_named_dollar_jurisdictions_and_other_reported_currencies_remain_distinct():
    for currency, expected in (("Australian dollars", "AUD"), ("euros", "EUR"), ("dollars", "dollar (jurisdiction not stated)")):
        result = build([P("g", f"Our FY25 revenue growth guidance is 3% to 4% in {currency}."),
                        P("o", "Our revenue growth for financial year 2025 was 5% in US dollars.", pub="2025-04-17T00:00:00+00:00")])
        item = find(result, "revenue_growth", "FY2024-25")
        assert not item["comparable"] and item["guidance"]["reporting_currency"] == expected


def test_generic_acquisition_question_and_management_reply_carry_both_citations():
    result = build([
        P("g", "Our FY25 revenue growth guidance is 4% to 5% in constant currency terms."),
        P("o", "Our revenue growth for financial year 2025 was 4.2% in constant currency terms.", pub="2025-04-17T00:00:00+00:00"),
        P("q", "How much of revenue growth was from the Exampleco acquisition?", speaker="An Analyst", page=6),
        P("a", "Exampleco added 20 basis points to revenue growth.", speaker="Jayesh Sanghrajka", page=6),
    ])
    item = find(result, "revenue_growth", "FY2024-25")
    assert any(c["evidence_ids"] == ["q", "a"] for c in item["caveats"])


def test_mixed_period_acquisition_paragraph_does_not_qualify_another_year():
    result = build([
        P("g", "Our FY25 revenue growth guidance is 4% to 5% in constant currency terms."),
        P("o", "Our revenue growth for financial year 2025 was 4.2% in constant currency terms.", pub="2025-04-17T00:00:00+00:00"),
        P("c", "Exiting FY25, we expect FY26 revenue growth of 3%. This excludes the acquisition announced today.", page=9),
    ])
    item = find(result, "revenue_growth", "FY2024-25")
    assert not any("acquisition" in c["text"] for c in item["caveats"])


def test_acquisition_pipeline_mention_is_not_a_growth_contribution():
    result = build([
        P("g", "Our FY25 revenue growth guidance is 4% to 5% in constant currency terms."),
        P("o", "Our revenue growth for financial year 2025 was 4.2% in constant currency terms.", pub="2025-04-17T00:00:00+00:00"),
        P("c", "The acquisition announced today will strengthen our vertical expertise. Our growth will be led by recent deal wins.", page=9),
    ])
    item = find(result, "revenue_growth", "FY2024-25")
    assert not any("acquisition" in c["text"] for c in item["caveats"])
