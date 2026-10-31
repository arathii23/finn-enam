"""Announcement prioritisation and EOD anomaly flags for the Push/review queue.

Judgment, not a model call: NSE's free-text `desc` is mapped to a reference category and an
attention tier, then refined by the filing subject/attachment so a generic 'Updates' that is
actually a transcript or results filing is not buried. Rules are explainable and deterministic.
Categories follow the assignment's companion reference document."""
from __future__ import annotations

import re
from statistics import mean
from typing import Any, Dict, List, Optional

# Attention tiers: 1 = leading (material), 2 = notable, 3 = routine (collapsed by default).
TIER_LEADING, TIER_NOTABLE, TIER_ROUTINE = 1, 2, 3

# NSE desc (lowercased substring) -> (reference_category, tier, reason)
_DESC_RULES: List[tuple] = [
    (r"outcome of board meeting", ("results", TIER_LEADING, "Board meeting outcome")),
    (r"financial result|clarification - financial|integrated filing- financial", ("results", TIER_LEADING, "Financial results")),
    (r"scheme of arrangement|amalgamation|\bmerger\b|demerger|acquisition|takeover|slump sale", ("M&A", TIER_LEADING, "M&A / restructuring")),
    (r"change in management|change in director|change in key managerial|resignation|cessation|appointment", ("management_change", TIER_LEADING, "Management / board change")),
    (r"fund rais|preferential|qualified institutional|\bqip\b|rights issue|\bbuyback\b|allotment of securities|commercial paper|non.?convertible", ("fund_raise", TIER_LEADING, "Fund raising / allotment")),
    (r"credit rating|rating action", ("credit_rating", TIER_LEADING, "Credit rating")),
    (r"order(s)? passed|penalty|litigation|insolvency|regulatory action|action\(s\) taken", ("litigation", TIER_LEADING, "Litigation / regulatory order")),
    (r"dividend", ("dividend", TIER_NOTABLE, "Dividend")),
    (r"capex|capacity|new plant|expansion", ("capex", TIER_NOTABLE, "Capex / expansion")),
    (r"con. call|conference call|earnings call|analysts/institutional|transcript", ("earnings_call", TIER_NOTABLE, "Earnings call / investor interaction")),
    (r"investor presentation|investor meet|investor/analyst", ("investor_meetings", TIER_NOTABLE, "Investor presentation / meeting")),
    (r"press release", ("press_release", TIER_NOTABLE, "Press release")),
    (r"related party", ("press_release", TIER_NOTABLE, "Related-party transactions")),
    (r"record date", ("dividend", TIER_NOTABLE, "Record date")),
    (r"shareholders meeting|postal ballot|annual general|extraordinary general|\bagm\b|\begm\b", ("agm_egm", TIER_NOTABLE, "Shareholder meeting")),
    (r"pledge|encumbrance", ("pledging", TIER_NOTABLE, "Promoter pledge")),
    (r"bonus|stock split|sub-division", ("bonus_split", TIER_NOTABLE, "Bonus / split")),
    (r"insider|sast|pit regulation", ("insider_trading", TIER_NOTABLE, "Insider / SAST disclosure")),
]
# Subject/attachment keyword refinements that can UPGRADE a generic label.
_REFINE_RULES: List[tuple] = [
    (r"transcript", ("earnings_call", TIER_NOTABLE, "Earnings-call transcript")),
    (r"earnings|investor release|investor presentation|result", ("results", TIER_LEADING, "Results-related filing")),
    (r"acqui|merger|amalgamation|scheme of arrangement|stake", ("M&A", TIER_LEADING, "M&A / restructuring")),
    (r"resign|appoint|cessation|director|cfo|ceo|managing director", ("management_change", TIER_LEADING, "Management / board change")),
]
_ROUTINE_HINT = re.compile(
    r"newspaper|loss of share|duplicate share|esop|esos|esps|trading window|certificate under sebi|"
    r"depositories and participants|general updates|compliance|reconciliation|voting results|scrutinizer", re.I)


def classify(category: Optional[str], subject: Optional[str] = None, attachment_url: Optional[str] = None) -> Dict[str, Any]:
    desc = (category or "").lower()
    hay = " ".join(x for x in (subject or "", attachment_url or "") if x).lower()
    ref, tier, reason = "unclassified", TIER_ROUTINE, "Routine / compliance"

    for pat, (r, t, why) in _DESC_RULES:
        if re.search(pat, desc):
            ref, tier, reason = r, t, why
            break
    else:
        # generic desc (e.g. 'Updates'): fall through to refinement below
        if _ROUTINE_HINT.search(desc):
            ref, tier, reason = "unclassified", TIER_ROUTINE, "Routine / compliance"

    # Refinement can upgrade (to a stronger tier) a generic or weaker classification.
    for pat, (r, t, why) in _REFINE_RULES:
        if re.search(pat, hay):
            if t < tier:
                ref, tier, reason = r, t, why
            break

    # A clearly routine subject never gets promoted above routine on desc alone.
    if tier == TIER_ROUTINE and _ROUTINE_HINT.search(hay) and not any(re.search(p, hay) for p, _ in _REFINE_RULES):
        reason = "Routine / compliance"
    return {"ref_category": ref, "tier": tier, "reason": reason}


def eod_anomaly(rows: List[Dict[str, Any]], price_move_pct: float, volume_multiple: float,
                baseline_sessions: int = 20, min_baseline: int = 5) -> Optional[Dict[str, Any]]:
    """Deterministic EOD flag on the latest session. rows ascending by trading_date.
    Baseline excludes the current session; raw (unadjusted) values; no causal claim."""
    rows = [r for r in rows if r.get("close") is not None]
    if not rows:
        return None
    latest = rows[-1]
    prior = rows[:-1]
    flags, notes = [], []

    price_move = None
    if latest.get("prev_close"):
        price_move = (latest["close"] - latest["prev_close"]) / latest["prev_close"] * 100.0
        if abs(price_move) >= price_move_pct:
            flags.append(f"price move {price_move:+.1f}% ≥ ±{price_move_pct:g}%")
    else:
        notes.append("no previous close; price-move check skipped")

    vol_ratio = None
    vols = [r["volume"] for r in prior if r.get("volume")][-baseline_sessions:]
    if latest.get("volume") and len(vols) >= min_baseline:
        base = mean(vols)
        if base > 0:
            vol_ratio = latest["volume"] / base
            if vol_ratio >= volume_multiple:
                flags.append(f"volume {vol_ratio:.1f}× the {len(vols)}-session average ≥ {volume_multiple:g}×")
    else:
        notes.append(f"insufficient volume history (<{min_baseline} prior sessions); volume ratio disabled")

    return {
        "trading_date": latest["trading_date"],
        "close": latest["close"], "prev_close": latest.get("prev_close"), "volume": latest.get("volume"),
        "price_move_pct": round(price_move, 2) if price_move is not None else None,
        "volume_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
        "flags": flags, "flagged": bool(flags), "basis": "raw (unadjusted) EOD", "notes": notes,
    }
