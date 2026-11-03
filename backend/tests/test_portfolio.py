"""Prioritisation and EOD-anomaly logic for the Push/review queue."""
from finn.prioritize import classify, eod_anomaly, TIER_LEADING, TIER_NOTABLE, TIER_ROUTINE


def test_material_categories_are_leading():
    assert classify("Outcome of Board Meeting")["tier"] == TIER_LEADING
    assert classify("Change in Management")["ref_category"] == "management_change"
    assert classify("Financial Result Updates")["ref_category"] == "results"
    assert classify("Action(s) taken or orders passed")["ref_category"] == "litigation"


def test_generic_updates_upgraded_by_subject():
    # NSE files the transcript under the generic 'Updates' desc; subject/attachment must rescue it.
    routine = classify("Updates", subject=None)
    assert routine["tier"] == TIER_ROUTINE
    transcript = classify("Updates", attachment_url="https://x/Infosys_..._Earningscalltranscript.pdf")
    assert transcript["ref_category"] == "earnings_call" and transcript["tier"] == TIER_NOTABLE
    acq = classify("Updates", subject="Intimation of acquisition of a company")
    assert acq["ref_category"] == "M&A" and acq["tier"] == TIER_LEADING


def test_routine_compliance_stays_collapsed():
    for d in ["Copy of Newspaper Publication", "Loss of Share Certificates", "ESOP/ESOS/ESPS",
              "Trading Window", "Certificate under SEBI (Depositories and Participants) Regulations, 2018"]:
        assert classify(d)["tier"] == TIER_ROUTINE, d


def test_filenames_do_not_override_specific_or_routine_exchange_categories():
    attachment = 'https://nsearchives.nseindia.com/corporate/TESTCO_Results_Q4.pdf'
    for category in ['Dividend', 'Record Date']:
        assert classify(category, 'Board of Directors recommends a dividend', attachment)['ref_category'] == 'dividend'
    assert classify('Copy of Newspaper Publication', 'Publication of audited financial results', attachment)['tier'] == TIER_ROUTINE
    assert classify('Appointment', 'Appointment of M/s. Example & Co., Company Secretaries', attachment)['tier'] == TIER_ROUTINE
    assert classify('Investor Presentation', 'Investor Presentation', attachment)['ref_category'] == 'investor_meetings'
    assert classify('Analysts/Institutional Investor Meet/Con. Call Updates', 'Call on financial results', attachment)['ref_category'] == 'earnings_call'


def test_call_notices_and_statutory_disclosures_are_not_results_or_company_acquisitions():
    assert classify('Updates', 'Intimation of Q4 FY2025 Earnings Conference Call')['ref_category'] == 'earnings_call'
    result = classify('Updates', 'A promoter has Submitted to the Exchange a copy of Disclosure under Regulation 31(4) of the Securities and Exchange Board of India (Substantial Acquisition of Shares and Takeovers) Regulations, 2011.')
    assert result['ref_category'] == 'insider_trading' and result['tier'] == TIER_NOTABLE
    assert classify('Acquisition', 'Acquisition of 100% equity stake of Example Limited')['ref_category'] == 'M&A'


def _bars(vols, closes, prevs):
    return [{"trading_date": f"2025-04-{10+i:02d}", "volume": v, "close": c, "prev_close": p}
            for i, (v, c, p) in enumerate(zip(vols, closes, prevs))]


def test_eod_price_and_volume_flags():
    rows = _bars([100]*6 + [250], [100]*6 + [108], [100]*7)  # 7th: +8% and 2.5x volume
    a = eod_anomaly(rows, price_move_pct=5.0, volume_multiple=2.0, min_baseline=5)
    assert a["flagged"] and a["price_move_pct"] == 8.0 and a["volume_ratio"] == 2.5
    assert len(a["flags"]) == 2


def test_eod_volume_ratio_disabled_without_history():
    rows = _bars([100, 300], [100, 101], [100, 100])  # only 1 prior session
    a = eod_anomaly(rows, 5.0, 2.0, min_baseline=5)
    assert a["volume_ratio"] is None and any("insufficient volume history" in n for n in a["notes"])
    assert not a["flagged"]  # +1% move, ratio disabled


def test_eod_requires_prev_close_for_price():
    rows = [{"trading_date": "2025-04-11", "volume": 100, "close": 100, "prev_close": None}]
    a = eod_anomaly(rows, 5.0, 2.0)
    assert a["price_move_pct"] is None and any("no previous close" in n for n in a["notes"])
