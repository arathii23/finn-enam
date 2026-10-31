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
