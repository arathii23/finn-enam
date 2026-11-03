"""Tests for the quarterly first-cut verification + arithmetic (no model)."""
from finn.quarterly import select_pnl_passages, validate_and_compute

PTEXT = ("Consolidated Statement of Financial Results (₹ crore). Three months ended 31 March 2025, 31 December 2024, "
         "31 March 2024. Revenue from operations 30,246 29,890 28,499. Profit before tax 5,100 4,900 4,600. "
         "Profit for the period 3,843 3,800 3,500.")
RAW_OK = {
    "basis": "consolidated",
    "columns": {"current_quarter_end": "2025-03-31", "previous_quarter_end": "2024-12-31",
                "year_ago_quarter_end": "2024-03-31"},
    "metrics": {
        "revenue": {"current": "30,246", "previous_quarter": "29,890", "year_ago_quarter": "28,499", "evidence_id": "p1", "unit": "₹ crore"},
        "ebitda": {"current": None, "previous_quarter": None, "year_ago_quarter": None, "evidence_id": None, "unit": None},
        "pbt": {"current": "5,100", "previous_quarter": "4,900", "year_ago_quarter": "4,600", "evidence_id": "p1", "unit": "₹ crore"},
        "pat": {"current": "3,843", "previous_quarter": "3,800", "year_ago_quarter": "3,500", "evidence_id": "p1", "unit": "₹ crore"},
    },
}


def test_computes_qoq_and_yoy_from_verified_numbers():
    r = validate_and_compute(RAW_OK, {"p1": PTEXT})
    rev = next(m for m in r["metrics"] if m["key"] == "revenue")
    assert rev["current"]["value"] == 30246
    assert rev["qoq_pct"] == round((30246 - 29890) / 29890 * 100, 1)
    assert rev["yoy_pct"] == round((30246 - 28499) / 28499 * 100, 1)
    assert r["columns"]["current"] == "Q4 FY2024-25"
    assert r["gates"] == {"qoq_comparable": True, "yoy_comparable": True}


def test_ebitda_omitted_when_not_in_statement():
    r = validate_and_compute(RAW_OK, {"p1": PTEXT})
    assert all(m["key"] != "ebitda" for m in r["metrics"])
    assert any(o["metric"] == "EBITDA" for o in r["omitted"])


def test_unverifiable_number_is_dropped():
    bad = {**RAW_OK, "metrics": {**RAW_OK["metrics"],
           "pat": {"current": "9,999", "previous_quarter": "3,800", "year_ago_quarter": "3,500", "evidence_id": "p1", "unit": None}}}
    r = validate_and_compute(bad, {"p1": PTEXT})
    # "9,999" is not in the passage -> no verified current value -> PAT omitted.
    assert all(m["key"] != "pat" for m in r["metrics"])
    assert any(o["metric"].startswith("Profit after tax") for o in r["omitted"])


def test_misaligned_columns_block_yoy():
    # year-ago date only 6 months back -> YoY not comparable, so year-ago values are dropped.
    raw = {**RAW_OK, "columns": {**RAW_OK["columns"], "year_ago_quarter_end": "2024-09-30"}}
    r = validate_and_compute(raw, {"p1": PTEXT})
    rev = next(m for m in r["metrics"] if m["key"] == "revenue")
    assert rev["yoy_pct"] is None and rev["year_ago_quarter"] is None
    assert rev["qoq_pct"] is not None  # QoQ still fine


def test_parentheses_are_negative():
    raw = {**RAW_OK, "metrics": {**RAW_OK["metrics"],
           "pbt": {"current": "(1,200)", "previous_quarter": "4,900", "year_ago_quarter": "4,600", "evidence_id": "p1", "unit": None}}}
    txt = PTEXT + " Profit before tax (1,200) 4,900 4,600."
    r = validate_and_compute(raw, {"p1": txt})
    pbt = next(m for m in r["metrics"] if m["key"] == "pbt")
    assert pbt["current"]["value"] == -1200


def test_select_pnl_passages_prefers_the_statement():
    ps = [
        {"passage_id": "x", "doc_type": "exchange_filing", "version_id": "v1", "page_index": 9, "text": "Thank you for joining."},
        {"passage_id": "a", "doc_type": "exchange_filing", "version_id": "v1", "page_index": 2, "text": "Three months ended 31 March 2025, 31 December 2024 and 31 March 2024. Revenue from operations 30,246 29,890 28,499."},
        {"passage_id": "b", "doc_type": "exchange_filing", "version_id": "v1", "page_index": 2, "text": "Profit before tax 5,100 4,900 4,600. Profit for the period 3,843."},
    ]
    sel = [p["passage_id"] for p in select_pnl_passages(ps)]
    assert "a" in sel and "b" in sel  # same-page statement travels together
    assert "x" not in sel             # unrelated page excluded


def test_completed_unreadable_filing_is_cached_without_retrying_a_model(env, monkeypatch):
    from dataclasses import replace
    from finn.ingest import ingest_replay
    from finn.replay import load_manifest
    from finn.service import App
    settings, store, fetcher, _ = env
    ingest_replay(store, fetcher, settings, load_manifest(settings.manifest_path), ["TESTCO"], log=lambda s: None)
    settings = replace(settings, openai_api_key="synthetic-unused")
    app = App(settings, store, client=object(), start_worker=False)
    calls = []
    monkeypatch.setattr("finn.quarterly.select_pnl_passages", lambda ps: ps[:1])
    def extract(*args):
        calls.append(True)
        return {"available": False, "reason": "No figures passed verification.", "generation": {"model": "synthetic", "usage": {}}}
    monkeypatch.setattr(app, "_extract_quarterly", extract)
    first = app.quarterly_results("TESTCO", allow_extract=True)
    second = app.quarterly_results("TESTCO")
    assert not first["available"] and not second["available"]
    assert second["served"] == "cached" and len(calls) == 1
    assert not store.query("SELECT * FROM model_calls")


def test_get_never_extracts_even_when_model_is_configured(env, monkeypatch):
    from dataclasses import replace
    from finn.ingest import ingest_replay
    from finn.replay import load_manifest
    from finn.service import App
    settings, store, fetcher, _ = env
    ingest_replay(store, fetcher, settings, load_manifest(settings.manifest_path), ["TESTCO"], log=lambda s: None)
    app = App(replace(settings, openai_api_key="synthetic-unused"), store, client=object(), start_worker=False)
    monkeypatch.setattr("finn.quarterly.select_pnl_passages", lambda ps: ps[:1])
    def forbidden(*args):
        raise AssertionError("A read must not trigger generation")
    monkeypatch.setattr(app, "_extract_quarterly", forbidden)
    result = app.quarterly_results("TESTCO")
    assert not result["available"] and result["can_extract"] and result["extraction_required"]
    assert not store.query("SELECT * FROM model_calls")


def test_exact_token_sign_and_metric_row_are_required():
    raw = {**RAW_OK, "metrics": {"revenue": {**RAW_OK["metrics"]["revenue"], "current": "246"}}}
    assert not validate_and_compute(raw, {"p1": PTEXT})["metrics"]
    wrong_row = {**RAW_OK, "metrics": {"revenue": {**RAW_OK["metrics"]["revenue"], "current": "5,100"}}}
    assert not validate_and_compute(wrong_row, {"p1": PTEXT})["metrics"]
    signed = {**RAW_OK, "metrics": {"pbt": {**RAW_OK["metrics"]["pbt"], "current": "1,200"}}}
    assert not validate_and_compute(signed, {"p1": PTEXT.replace("5,100", "(1,200)")})["metrics"]


def test_explicit_ebitda_label_is_enforced_in_code():
    raw = {**RAW_OK, "metrics": {"ebitda": dict(RAW_OK["metrics"]["revenue"])}}
    assert not validate_and_compute(raw, {"p1": PTEXT})["metrics"]
    labelled = PTEXT.replace("Revenue from operations", "EBITDA")
    assert validate_and_compute(raw, {"p1": labelled})["metrics"][0]["key"] == "ebitda"


def test_plausible_dates_must_be_printed_and_be_exact_quarter_ends():
    invented = {**RAW_OK, "columns": {"current_quarter_end": "2026-03-31", "previous_quarter_end": "2025-12-31", "year_ago_quarter_end": "2025-03-31"}}
    assert not validate_and_compute(invented, {"p1": PTEXT})["metrics"]
    invalid = {**RAW_OK, "columns": {**RAW_OK["columns"], "current_quarter_end": "2025-03-30"}}
    assert not validate_and_compute(invalid, {"p1": PTEXT.replace("31 March 2025", "30 March 2025")})["metrics"]
    annual = PTEXT.replace("Three months ended", "Annual balance sheet as of")
    assert not validate_and_compute(RAW_OK, {"p1": annual})["metrics"]


def test_conflicting_basis_or_unit_is_rejected_and_missing_currency_not_invented():
    assert not validate_and_compute(RAW_OK, {"p1": PTEXT.replace("Consolidated", "Standalone")})["metrics"]
    wrong = {**RAW_OK, "metrics": {"revenue": {**RAW_OK["metrics"]["revenue"], "unit": "USD billion"}}}
    assert not validate_and_compute(wrong, {"p1": PTEXT})["metrics"]
    unknown_currency = validate_and_compute(RAW_OK, {"p1": PTEXT.replace("₹ crore", "in crores")})
    assert unknown_currency["metrics"] and all(m["unit"] == "crore (currency not identified)" for m in unknown_currency["metrics"])
    assert unknown_currency["warnings"]


def test_same_page_context_supports_a_split_table_header():
    text = "Consolidated statement (₹ crore)\nThree months ended\n31March 31December 31 March\n2025 2024 2024\n"
    row = "Revenue from operations 30,246 29,890 28,499"
    raw = {**RAW_OK, "metrics": {"revenue": RAW_OK["metrics"]["revenue"]}}
    result = validate_and_compute(raw, {"p1": row}, {"p1": text + row})
    assert len(result["metrics"]) == 1 and result["gates"]["qoq_comparable"]


def test_reversed_or_annual_column_values_are_rejected():
    swapped = {**RAW_OK, "metrics": {"revenue": {**RAW_OK["metrics"]["revenue"], "current": "28,499", "year_ago_quarter": "30,246"}}}
    assert not validate_and_compute(swapped, {"p1": PTEXT})["metrics"]
    dates = "Consolidated (₹ crore). Three months ended 31/03/2025 31/12/2024 31/03/2024 Year ended 31/03/2025 31/03/2024\n"
    text = dates + "Revenue from operations 30,246 29,890 28,499 117,055 109,913"
    annual = {**RAW_OK, "metrics": {"revenue": {**RAW_OK["metrics"]["revenue"], "current": "117,055"}}}
    assert not validate_and_compute(annual, {"p1": text})["metrics"]


def test_explicit_segment_total_not_an_individual_segment_is_bound_to_dates():
    text = "Business Segments (₹ crore)\nParticulars Segment A Segment B Total\nRevenue from operations 100 200 300\n90 180 270\nThree months ended March 31, 2025 and March 31, 2024"
    raw = {"basis": "", "columns": {"current_quarter_end": "2025-03-31", "previous_quarter_end": "", "year_ago_quarter_end": "2024-03-31"},
           "metrics": {"revenue": {"current": "300", "previous_quarter": "", "year_ago_quarter": "270", "unit": "₹ crore", "evidence_id": "p"}}}
    result = validate_and_compute(raw, {"p": text})
    assert result["metrics"][0]["yoy_pct"] == 11.1
    raw["metrics"]["revenue"].update(current="100", year_ago_quarter="90")
    assert not validate_and_compute(raw, {"p": text})["metrics"]


def test_selector_never_combines_filing_versions_or_asset_notes():
    ps = [
        {"passage_id": "old", "doc_type": "exchange_filing", "version_id": "old", "page_index": 1, "text": PTEXT.replace("2025", "2024").replace("2024", "2023")},
        {"passage_id": "new", "doc_type": "exchange_filing", "version_id": "new", "page_index": 2, "text": PTEXT},
        {"passage_id": "note", "doc_type": "exchange_filing", "version_id": "new", "page_index": 78, "text": "Three months ended March 31, 2025. Depreciation and finance cost " * 20},
    ]
    result = select_pnl_passages(ps)
    assert [p["passage_id"] for p in result] == ["new"]


def test_legacy_cache_is_revalidated_in_memory_with_actual_metric_page(env, monkeypatch):
    import json
    from finn.ingest import ingest_replay
    from finn.replay import load_manifest
    from finn.service import App
    settings, store, fetcher, _ = env
    ingest_replay(store, fetcher, settings, load_manifest(settings.manifest_path), ["TESTCO"], log=lambda s: None)
    v = store.query_one("SELECT * FROM document_versions WHERE doc_type='exchange_filing'")
    store.execute("INSERT INTO passages (passage_id,version_id,page_index,text,extraction_status,seq) VALUES (?,?,?,?,?,?)",
                  ("p1", v["version_id"], 9, PTEXT, "extracted", 100))
    saved = {"available": True, "source": {"version_id": v["version_id"], "page_index": 1}, **validate_and_compute(RAW_OK, {"p1": PTEXT})}
    serialized = json.dumps(saved)
    store.execute("INSERT INTO derived_cache VALUES (?,?,?,?)", ("quarterly:isin:INE000T01011:legacy", "quarterly", serialized, "2025-04-25T00:00:00+00:00"))
    app = App(settings, store, client=None, start_worker=False)
    result = app.quarterly_results("TESTCO")
    assert result["available"] and result["served"] == "cached"
    assert result["source"]["page_index"] == 9
    assert all(m["source"]["page_index"] == 9 for m in result["metrics"])
    assert store.query_one("SELECT result FROM derived_cache")["result"] == serialized
    assert not store.query("SELECT * FROM model_calls")
