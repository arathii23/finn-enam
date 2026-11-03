"""Numbers vs Narrative — deterministic promised-vs-delivered comparison.

This is the "analyse management, don't just summarise them" view. It lines up what
management *guided* (from an earnings-call transcript) against what the company
*delivered* (from a later call or results filing), and only states a verdict when a
hard comparability gate passes: same metric, same fiscal period, same currency basis
(constant-currency vs reported) and same reporting entity (standalone vs consolidated).

Design rules, all enforced here rather than trusted to a model:
  * No model call. Guidance and outcome statements are extracted from primary-source
    passages by explicit rules; every number is verified to appear verbatim in its
    cited passage before it can be used.
  * Arithmetic is deterministic Python. We never ask a model to compare numbers.
  * Where the gate fails or no outcome exists yet, we show both source passages with
    the explicit reason (not comparable / outcome pending) and no verdict.
  * No investment advice, no beat/miss framing, no red/green. The verdict is a factual
    statement of the arithmetic gap, traceable to exact PDF pages.

The engine is generic. It recognises the guidance/outcome patterns that recur across
large-cap NSE transcripts (headline revenue growth and operating margin, as %/range,
annual vs quarterly, constant-currency vs reported). For a company whose disclosures do
not yield a confident comparable pair, it returns nothing rather than guessing.
"""
from __future__ import annotations

import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Metrics we know how to line up, with display label and a plausibility range (%) that a
# value must fall in to count as that metric. The range is a slop filter: an EPS or
# free-cash-flow percentage that drifts near the words we key on is rejected, not reported.
_METRICS = {
    "revenue_growth": {"label": "Revenue growth", "lo": -25.0, "hi": 40.0},
    "operating_margin": {"label": "Operating margin", "lo": 5.0, "hi": 60.0},
}

# Words that, when they govern the number more closely than a metric word, disqualify it:
# these are other percentages that live in the same sentences (EPS, cash flow, attrition,
# or a segment's share of revenue — a mix, not a growth rate).
_DISQUALIFY = re.compile(r"eps|per share|cash flow|\bfcf\b|net profit|profit after tax|\bpat\b|\bpbt\b|"
                         r"attrition|utiliz|utilis|headcount|hiring|freshers|dividend|payout|tax rate|"
                         r"basis points|\bbps\b|net addition|pricing|\btcv\b|large deal|book|voln|volume|"
                         r"shareholding|pledge|stake|interim|final dividend|yield|roce|\broe\b|"
                         r"contribut|\bmix\b|\bshare of\b", re.I)
# A figure immediately followed by "of/to … revenue" is a segment's share of revenue (mix),
# not a growth rate — e.g. "contributed 37% to our revenues".
_CONTRIBUTION = re.compile(r"^\s*(?:of|to)\s+(?:our\s+|the\s+|total\s+)*revenue", re.I)

# A statement is forward-looking (guidance) if any of these cues sit near the number.
_GUIDANCE_CUE = re.compile(r"\bguidance\b|\bguiding\b|\bwe guide\b|\bwe expect\b|\bexpect(?:s|ed)?\s+(?:fy|financial|revenue|growth|margin|to)\b|\boutlook\b|revising our|\bwe aim\b|\baspire", re.I)
# Realised-outcome cues (only consulted when there is no guidance cue nearby).
_OUTCOME_CUE = re.compile(r"\bgrew\b|\bgrowth of\b|\bended the year\b|\bdelivered\b|\bwe had\b|\bposted\b|\bgenerated\b|\bcame in\b|\bwas\b|\bstood at\b|\breported\b", re.I)

# Quarter-scoped language (these numbers are not full-year figures).
_QUARTERLY = re.compile(r"quarter-on-quarter|q-?o-?q|sequential(?:ly)?|year-on-year|y-?o-?y|"
                        r"this quarter|in the quarter|for the quarter|\bquarters?\b|\bq[1-4]\b", re.I)
# Full-year language.
_ANNUAL = re.compile(r"financial year|fiscal year|\bfor the year\b|\bfull[- ]year\b|ended the year|\bfor fiscal\b|\bannual\b|\bfy['\s]?\d", re.I)
_SEGMENT_SCOPE = re.compile(r"\b(?:segment|subsidiar(?:y|ies)|division|business unit|vertical|geograph(?:y|ies)|region)\b", re.I)

_SIGNED = r"[+\-−]?\d+(?:\.\d+)?"
_RANGE = re.compile(r"(?<![\d.])(" + _SIGNED + r")\s*%?\s*(?:-|to|–|—)\s*(" + _SIGNED + r")\s*%")
_SINGLE = re.compile(r"(?<![\d.])(" + _SIGNED + r")\s*%")
_CURRENCIES = {
    "INR": r"\b(?:INR|rupees?)\b|₹",
    "USD": r"\bUSD\b|\bU\.?S\.?\s+dollars?\b|\bUnited States dollars?\b",
    "EUR": r"\b(?:EUR|euros?)\b|€",
    "GBP": r"\b(?:GBP|sterling|pounds?)\b|£",
    "JPY": r"\b(?:JPY|yen)\b",
    "CNY": r"\b(?:CNY|RMB|renminbi)\b",
    "AUD": r"\bAUD\b|\bAustralian dollars?\b",
    "CAD": r"\bCAD\b|\bCanadian dollars?\b",
    "SGD": r"\bSGD\b|\bSingapore dollars?\b",
    "HKD": r"\bHKD\b|\bHong Kong dollars?\b",
    "AED": r"\b(?:AED|dirhams?)\b",
    "CHF": r"\bCHF\b|\bSwiss francs?\b",
}


def _fiscal_end_years(text: str) -> List[int]:
    """Indian fiscal years (ending in March) named in the text, as end-year ints.

    "financial year 2025" / "FY2024-25" / "FY'25" / "fiscal 2025" -> 2025.
    """
    years: List[int] = []
    for m in re.finditer(r"(?:financial year|fiscal year|fiscal)\s*'?(\d{2,4})", text, re.I):
        years.append(_norm_year(m.group(1)))
    for m in re.finditer(r"\bFY\s*'?(\d{2})(?:\s*-\s*(\d{2}))?\b", text, re.I):
        years.append(_norm_year(m.group(2) or m.group(1)))
    for m in re.finditer(r"\bFY\s*'?(\d{4})\s*-\s*(\d{2,4})\b", text, re.I):
        years.append(_norm_year(m.group(2)))
    return [y for y in years if y]


def _norm_year(token: str) -> int:
    n = int(token)
    if n < 100:
        n += 2000
    return n


def fy_label(end_year: int) -> str:
    """Canonical period label matching the corpus, e.g. 2025 -> 'FY2024-25'."""
    return f"FY{end_year - 1}-{str(end_year)[-2:]}"


def _call_end_year(period_label: Optional[str]) -> Optional[int]:
    if not period_label:
        return None
    m = re.search(r"FY(\d{4})-(\d{2})", period_label)
    if m:
        return int(m.group(1)) + 1
    return None


def _call_quarter(period_label: Optional[str]) -> Optional[int]:
    if not period_label:
        return None
    m = re.search(r"\bQ([1-4])\b", period_label)
    return int(m.group(1)) if m else None


def _split_sentences(text: str) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


@dataclass
class Statement:
    kind: str            # "guidance" | "outcome"
    metric: str          # key in _METRIC_KEYWORDS
    basis: str           # "constant_currency" | "reported"
    fiscal_year: int     # end year (e.g. 2025)
    low: float
    high: float          # == low for a single value
    value_text: str      # verbatim snippet, e.g. "4.5% to 5%"
    evidence_id: str
    speaker: Optional[str]
    call_period: Optional[str]
    published_at: Optional[str]
    doc_type: str
    entity: str = "not stated"
    reporting_currency: str = "not stated"


_METRIC_WORDS = [("operating margin", "margin"), ("margin band", "margin"), ("margin", "margin"),
                 ("revenues", "revenue"), ("revenue", "revenue"), ("growth", "growthword"), ("grew", "growthword")]


def _classify_metric(sentence: str, start: int, end: int) -> Optional[str]:
    """Decide which metric (if any) governs the number spanning [start, end) in a sentence.

    The governing word is the metric or disqualifier token closest to the number on either
    side — "margin" (as in "margin of 21.1%" or "21.1% operating margin") means operating
    margin; "revenue"/"growth"/"grew" means revenue growth, but only when the figure is a
    genuine revenue / constant-currency growth number, not EPS or cash-flow growth. A number
    governed most closely by a disqualifier (EPS, dividend, attrition, …) is rejected.
    """
    low = sentence.lower()
    marks: List[Tuple[int, str]] = []

    def dist(ms: int, me: int) -> int:
        return (start - me) if me <= start else (ms - end) if ms >= end else 0

    for kw, kind in _METRIC_WORDS:
        for m in re.finditer(re.escape(kw), low):
            marks.append((dist(m.start(), m.end()), kind))
    for m in _DISQUALIFY.finditer(low):
        marks.append((dist(m.start(), m.end()), "bad"))
    if not marks:
        return None
    marks.sort(key=lambda x: x[0])
    nearest = marks[0][1]
    if nearest == "bad":
        return None
    if nearest == "margin":
        return "operating_margin"
    if nearest == "revenue":
        return "revenue_growth"
    if nearest == "growthword" and re.search(r"revenue|constant currency|financial year|\bfy", sentence, re.I):
        return "revenue_growth"
    return None


def extract_statements(passages: List[Dict[str, Any]], management: Optional[set] = None) -> List[Statement]:
    """Pull guidance/outcome statements from transcript and results-filing passages.

    Each number in a passage is attributed from its own sentence, so one passage can yield
    several statements (e.g. a revenue figure and a margin figure). Transcript passages are
    accepted only from verified management speakers — an analyst restating a number on the
    call is not treated as the company's guidance or outcome.
    """
    mgmt = {m.strip().lower() for m in (management or set())}
    out: List[Statement] = []
    for p in passages:
        if p.get("doc_type") not in ("earnings_call_transcript", "exchange_filing"):
            continue
        if p.get("doc_type") == "earnings_call_transcript":
            spk = (p.get("speaker") or "").strip().lower()
            if not mgmt or spk not in mgmt:
                continue
        full = re.sub(r"\s+", " ", p.get("text") or "")
        call_q = _call_quarter(p.get("period_label"))
        call_fy = _call_end_year(p.get("period_label"))
        # Attribute each number within its own sentence, so a "versus FY'25" aside in one
        # sentence can never label the next sentence's guidance with the wrong fiscal year.
        for sent in _split_sentences(full):
            if _SEGMENT_SCOPE.search(sent):
                continue  # explicit sub-entity figures are not issuer-wide metrics
            seen_spans: List[Tuple[int, int]] = []
            for rx, is_range in ((_RANGE, True), (_SINGLE, False)):
                for m in rx.finditer(sent):
                    span = m.span()
                    if any(not (span[1] <= s or span[0] >= e) for s, e in seen_spans):
                        continue  # a single already counted inside a matched range
                    seen_spans.append(span)
                    metric = _classify_metric(sent, span[0], span[1])
                    if metric is None:
                        continue
                    if _QUARTERLY.search(sent):
                        continue  # quarter figures are not full-year guidance/outcome
                    if _CONTRIBUTION.match(sent[span[1]:]):
                        continue  # "37% of revenue" is a mix, not a growth rate
                    annual = bool(_ANNUAL.search(sent))
                    years = _fiscal_end_years(sent)
                    if _GUIDANCE_CUE.search(sent):
                        kind = "guidance"
                    elif _OUTCOME_CUE.search(sent) or (years and annual):
                        # a figure stated for a named fiscal year with no forward cue is a
                        # reported outcome, e.g. "financial year 2025 – 4.2% growth".
                        kind = "outcome"
                    else:
                        continue
                    # Fiscal year, attributed conservatively from the sentence itself:
                    if len(set(years)) > 1:
                        continue  # a sentence naming two years cannot safely label this figure
                    if years:
                        fy = years[0]
                    elif kind == "outcome" and annual:
                        fy = call_fy                      # the year just reported on this call
                    elif kind == "guidance" and call_q in (1, 2, 3) and re.search(r"\bguidance\b", sent, re.I):
                        fy = call_fy                      # explicit "guidance" with no year on a
                    else:                                 # mid-year call = the current fiscal year
                        continue                          # otherwise do not guess the year
                    if not fy:
                        continue
                    basis = "constant_currency" if re.search(r"constant currency", sent, re.I) else "reported"
                    if metric == "operating_margin":
                        basis = "reported"  # margins are reported, never constant-currency
                    reporting_currency = "not applicable" if metric == "operating_margin" else "constant currency" if basis == "constant_currency" else "not stated"
                    if metric == "revenue_growth" and basis == "reported":
                        currencies = {currency for currency, pattern in _CURRENCIES.items()
                                      if re.search(pattern, sent, re.I)}
                        if len(currencies) > 1:
                            continue
                        reporting_currency = next(iter(currencies), "not stated")
                        if not currencies and re.search(r"\bdollars?\b|\$", sent, re.I):
                            reporting_currency = "dollar (jurisdiction not stated)"
                    low = float(m.group(1).replace("−", "-"))
                    high = float(m.group(2).replace("−", "-")) if is_range else low
                    if low > high:
                        continue
                    scopes = set(re.findall(r"\b(standalone|consolidated)\b", sent, re.I))
                    if not scopes:
                        scopes = set(re.findall(r"\b(standalone|consolidated)\b", full, re.I))
                    scopes = {s.lower() for s in scopes}
                    if len(scopes) > 1:
                        continue
                    entity = next(iter(scopes), "not stated")
                    rng = _METRICS[metric]
                    if not (rng["lo"] <= low <= rng["hi"] and rng["lo"] <= high <= rng["hi"]):
                        continue  # value implausible for this metric; likely a mis-grab
                    # verbatim guard: the numbers must be present in the passage text
                    toks = {m.group(1)} | ({m.group(2)} if is_range else set())
                    if not all(re.search(r"(?<!\d)" + re.escape(t) + r"(?!\d)", full) for t in toks):
                        continue
                    out.append(Statement(kind=kind, metric=metric, basis=basis, fiscal_year=fy,
                                         low=low, high=high, value_text=m.group(0).strip(),
                                         evidence_id=p["passage_id"], speaker=p.get("speaker"),
                                         call_period=p.get("period_label"), published_at=p.get("published_at"),
                                         doc_type=p.get("doc_type"), entity=entity,
                                         reporting_currency=reporting_currency))
    return out


def _dedup(statements: List[Statement], kind: str) -> Dict[Tuple[str, int, str, str, str], Statement]:
    """Keep one statement per metric/year/basis/entity/currency; then prefer latest transcript."""
    best: Dict[Tuple[str, int, str, str, str], Statement] = {}
    for s in (x for x in statements if x.kind == kind):
        key = (s.metric, s.fiscal_year, s.basis, s.entity, s.reporting_currency)
        cur = best.get(key)
        if cur is None:
            best[key] = s
            continue
        s_pref = (s.doc_type != "earnings_call_transcript", s.published_at or "")
        c_pref = (cur.doc_type != "earnings_call_transcript", cur.published_at or "")
        # transcript wins; among same doc kind, later publication wins
        if (not s_pref[0], s_pref[1]) > (not c_pref[0], c_pref[1]):
            best[key] = s
    return best


_BASIS_LABEL = {"constant_currency": "constant currency", "reported": "reported"}


def _caveats(metric: str, fiscal_year: int, passages: List[Dict[str, Any]],
             management: Optional[set]) -> List[Dict[str, Any]]:
    """Source-derived comparability notes (generic, cited — never asserted from memory).

    Uses generic acquisition language, including a management reply to an adjacent
    source-cited question that establishes the acquisition referent. No company or
    acquisition name is hardcoded. A question alone never establishes a contribution.
    """
    if metric != "revenue_growth":
        return []
    mgmt = {m.strip().lower() for m in (management or set())}
    best = None
    for i, p in enumerate(passages):
        if p.get("doc_type") != "earnings_call_transcript":
            continue
        if (p.get("speaker") or "").strip().lower() not in mgmt:
            continue
        years = set(_fiscal_end_years(p.get("text") or ""))
        if len(years) > 1:
            continue  # do not attach a mixed-period acquisition paragraph to one year's outcome
        if years and fiscal_year not in years:
            continue
        if not years and _call_end_year(p.get("period_label")) != fiscal_year:
            continue
        acquisition = re.compile(r"\binorganic\b|\bacquisition\b|\bacquired\b", re.I)
        text = re.sub(r"\s+", " ", p.get("text") or "")
        contribution = re.search(
            r"\binorganic\b.{0,100}\b(?:growth|revenues?|contribut\w*)\b|"
            r"\b(?:growth|revenues?|contribut\w*)\b.{0,100}\binorganic\b|"
            r"\bacquisitions?\b.{0,100}\b(?:contribut\w*|added)\b|"
            r"\b(?:contribut\w*|added)\b.{0,100}\bacquisitions?\b", text, re.I)
        context_ids = []
        if not contribution:
            previous = [q for q in passages[:i] if q.get("version_id") == p.get("version_id")
                        and q.get("page_index") == p.get("page_index")]
            question = previous[-1] if previous else None
            if not question or "?" not in (question.get("text") or "") or not acquisition.search(question.get("text") or ""):
                continue
            question_years = set(_fiscal_end_years(question.get("text") or ""))
            if len(question_years) > 1 or (question_years and fiscal_year not in question_years):
                continue
            context_ids.append(question["passage_id"])
        if not re.search(r"growth|revenue|contribut", p.get("text") or "", re.I):
            continue
        is_mgmt = (p.get("speaker") or "").strip().lower() in mgmt
        if best is None or (is_mgmt and not best[1]):
            best = (context_ids + [p["passage_id"]], is_mgmt)
    if best is None:
        return []
    return [{"text": "Management discussed inorganic (acquisition) contributions in this period's call. "
                     "Review the cited scope before treating this as an organic-growth comparison.",
             "evidence_ids": best[0]}]


def _verdict(guidance: Statement, outcome: Statement) -> Dict[str, Any]:
    v = round(outcome.low, 4)
    lo, hi = guidance.low, guidance.high
    rng = f"{_fmt(lo)}–{_fmt(hi)}%" if hi != lo else f"{_fmt(lo)}%"
    if v < lo:
        return {"kind": "below_range", "delta_pp": round(v - lo, 2),
                "summary": f"Delivered {_fmt(v)}% — {_fmt(abs(round(v - lo, 2)))}pp below the {rng} guided range."}
    if v > hi:
        return {"kind": "above_range", "delta_pp": round(v - hi, 2),
                "summary": f"Delivered {_fmt(v)}% — {_fmt(round(v - hi, 2))}pp above the {rng} guided range."}
    return {"kind": "within_range", "delta_pp": 0.0,
            "summary": f"Delivered {_fmt(v)}% — within the {rng} guided range."}


def _fmt(x: float) -> str:
    return (f"{x:.1f}".rstrip("0").rstrip(".")) if x != int(x) else str(int(x))


def _stmt_json(s: Statement) -> Dict[str, Any]:
    return {"value_text": s.value_text, "low": s.low, "high": s.high, "basis": _BASIS_LABEL[s.basis],
            "evidence_id": s.evidence_id, "speaker": s.speaker, "source_period": s.call_period,
            "published_at": s.published_at, "doc_type": s.doc_type, "entity": s.entity,
            "reporting_currency": s.reporting_currency}


def _later(outcome: Statement, guidance: Statement) -> bool:
    try:
        o, g = datetime.fromisoformat(outcome.published_at or ""), datetime.fromisoformat(guidance.published_at or "")
        return o.tzinfo is not None and g.tzinfo is not None and o > g
    except (ValueError, TypeError):
        return False


def build_narrative_numbers(symbol: str, legal_name: str, passages: List[Dict[str, Any]],
                            cutoff_display: Optional[str], cutoff_end_year: Optional[int] = None,
                            management: Optional[set] = None) -> Dict[str, Any]:
    """Assemble the promised-vs-delivered items for a company from its passages."""
    statements = extract_statements(passages, management)
    guides = _dedup(statements, "guidance")
    outcomes = _dedup(statements, "outcome")

    items: List[Dict[str, Any]] = []
    for key, g in sorted(guides.items(), key=lambda kv: (-kv[0][1], kv[0][0])):
        metric, fy, basis, entity, reporting_currency = key
        label = _METRICS[metric]["label"]
        o = outcomes.get(key)
        # cross-basis outcome (e.g. guided CC, only reported outcome available)
        o_other = next((outcomes[k] for k in outcomes if k[0] == metric and k[1] == fy and k[2] != basis and k[3] == entity), None)
        o_entity = next((outcomes[k] for k in outcomes if k[0] == metric and k[1] == fy and k[2] == basis and k[3] != entity), None)
        o_currency = next((outcomes[k] for k in outcomes if k[:4] == key[:4] and k[4] != reporting_currency), None)
        item: Dict[str, Any] = {
            "metric": label, "metric_key": metric, "fiscal_year": fy_label(fy),
            "basis": _BASIS_LABEL[basis], "entity": entity, "reporting_currency": reporting_currency,
            "guidance": _stmt_json(g),
            "caveats": _caveats(metric, fy, passages, management),
        }
        if entity == "not stated":
            item["caveats"].append({
                "text": "These issuer-level statements do not explicitly restate standalone or consolidated scope. "
                        "Their reporting-entity equality is not independently established here.",
                "evidence_ids": list(dict.fromkeys([g.evidence_id] + ([o.evidence_id] if o else [])))})
        if metric == "revenue_growth" and basis == "reported" and reporting_currency not in _CURRENCIES:
            item["caveats"].append({
                "text": "The reported-growth currency is not explicitly identified in these statements. "
                        "Their currency equality is not independently established here.",
                "evidence_ids": list(dict.fromkeys([g.evidence_id] + ([o.evidence_id] if o else [])))})
        if o is not None and not _later(o, g):
            item["outcome"] = _stmt_json(o)
            item["comparable"] = False
            item["gate_reasons"] = ["The outcome must have a verified publication time later than the guidance."]
            item["verdict"] = {"kind": "not_comparable", "delta_pp": None,
                               "summary": "Not comparable: publication order does not establish a later delivered outcome."}
        elif o is not None:
            item["outcome"] = _stmt_json(o)
            item["comparable"] = True
            item["gate_reasons"] = []
            item["verdict"] = _verdict(g, o)
            # If a same-metric, same-year figure also exists on the other currency basis,
            # note it so a reviewer sees FINN deliberately did not compare across bases.
            if o_other is not None:
                item.setdefault("caveats", []).append({
                    "text": f"A {_BASIS_LABEL[o_other.basis]} figure of {o_other.value_text} also exists for "
                            f"{fy_label(fy)}; it is not compared against {_BASIS_LABEL[basis]} guidance, because "
                            f"a {_BASIS_LABEL[basis]} target and a {_BASIS_LABEL[o_other.basis]} result are not like-for-like.",
                    "evidence_ids": [o_other.evidence_id]})
        elif o_currency is not None:
            item["outcome"] = _stmt_json(o_currency)
            item["comparable"] = False
            item["gate_reasons"] = [f"Reported currency differs or is not stated: guidance is {reporting_currency}; outcome is {o_currency.reporting_currency}."]
            item["verdict"] = {"kind": "not_comparable", "delta_pp": None,
                               "summary": "Not comparable: the reported-growth currencies are not matched."}
        elif o_entity is not None:
            item["outcome"] = _stmt_json(o_entity)
            item["comparable"] = False
            item["gate_reasons"] = [f"Reporting entity differs or is not stated: guidance is {entity}; outcome is {o_entity.entity}."]
            item["verdict"] = {"kind": "not_comparable", "delta_pp": None,
                               "summary": "Not comparable: reporting-entity scope is not matched."}
        elif o_other is not None:
            item["outcome"] = _stmt_json(o_other)
            item["comparable"] = False
            item["gate_reasons"] = [f"Currency basis differs: guidance is {_BASIS_LABEL[basis]}, "
                                    f"the available outcome is {_BASIS_LABEL[o_other.basis]}."]
            item["verdict"] = {"kind": "not_comparable", "delta_pp": None,
                               "summary": "Not comparable: the guided and delivered figures use different currency bases."}
        else:
            item["outcome"] = None
            item["comparable"] = False
            item["gate_reasons"] = []
            pending_future = cutoff_end_year is not None and fy >= cutoff_end_year
            item["verdict"] = {"kind": "pending", "delta_pp": None,
                               "summary": (f"Outcome for {fy_label(fy)} is not yet knowable"
                                           + (f" as of {cutoff_display}." if cutoff_display else ".")) if pending_future
                               else f"No delivered figure for {fy_label(fy)} was found in the eligible primary sources."}
        items.append(item)

    # Order: resolved comparisons first, then pending, then not-comparable.
    rank = {"below_range": 0, "above_range": 0, "within_range": 0, "pending": 1, "not_comparable": 2}
    items.sort(key=lambda it: (rank.get(it["verdict"]["kind"], 3), it["fiscal_year"]))

    return {
        "symbol": symbol, "legal_name": legal_name, "cutoff_display": cutoff_display,
        "items": items,
        "method": "Guidance and outcome figures are extracted verbatim from primary-source transcripts and "
                  "results filings, matched within the same metric, fiscal year, currency basis, reported currency and stated reporting entity, and "
                  "compared with deterministic arithmetic. No model generates or judges these numbers.",
        "empty_reason": None if items else
            "No comparable headline guidance (revenue growth or operating margin) was found in this company's "
            "eligible transcripts. FINN shows a verdict only when the sources support one.",
    }
