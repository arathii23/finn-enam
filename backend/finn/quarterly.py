"""Quarterly-results first cut (Push side): Revenue / EBITDA / PBT / PAT, QoQ and YoY.

Headline numbers are read from the company's actual results filing. Indian results PDFs are
wildly heterogeneous — clean columnar statements, scanned/garbled tables, bank formats — so a
cheap model (Haiku) does the bulk table reading, and everything it returns is then checked
deterministically here:
  * every value must appear verbatim in its cited filing passage (no fabrication);
  * the three column dates must look like consecutive quarter (QoQ) and year-ago (YoY) periods,
    or the metric is dropped (guards against column misalignment on a messy table);
  * QoQ/YoY percentages are computed in Python, never by the model;
  * EBITDA is taken only if the statement labels it — it is never derived or guessed.
A metric that fails any check is omitted with a reason rather than shown wrong. This is the
"gate on table-extraction confidence; omit rather than guess" rule from the brief.
"""
from __future__ import annotations

import re
import math
import calendar
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

_METRICS = [("revenue", "Revenue"), ("ebitda", "EBITDA"),
            ("pbt", "Profit before tax (PBT)"), ("pat", "Profit after tax (PAT)")]

_ROW_HINTS = ("revenue from operation", "total income", "total revenue", "interest earned",
              "profit before tax", "profit for the period", "profit after tax", "net profit",
              "total expenses", "ebitda", "depreciation", "finance cost")

VALIDATION_VERSION = "quarterly-source-v2"
_LABELS = {
    "revenue": r"\b(?:revenue from operations?|total revenue|interest earned)\b",
    "ebitda": r"\bEBITDA\b",
    "pbt": r"\bprofit\s+before\s+tax(?:\s+expense)?\b",
    "pat": r"\b(?:profit\s+for\s+the\s+period(?:\s*/\s*year)?|net\s+prof[i1][t1](?:\s+for\s+the\s+period)?)\b",
}
_QUARTER = re.compile(r"\bquarter\b|\bthree\s+months\b|\b3\s+months\b", re.I)
_TOKEN = re.compile(r"(?<![\w.,])(?:\([+-]?\d(?:[\d,]*\d)?(?:\.\d+)?\)|[+-]?\d(?:[\d,]*\d)?(?:\.\d+)?)(?![\w,]|\.\d)")
_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_MONTH_NO = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}

# All fields are plain strings (empty string = absent). Structured-output schemas cap the
# number of nullable/union-typed parameters, so we avoid nulls entirely and treat "" as missing.
_STR = {"type": "string"}
EXTRACT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["basis", "columns", "metrics"],
    "properties": {
        "basis": _STR,
        "columns": {"type": "object", "additionalProperties": False,
                    "required": ["current_quarter_end", "previous_quarter_end", "year_ago_quarter_end"],
                    "properties": {k: _STR for k in
                                   ("current_quarter_end", "previous_quarter_end", "year_ago_quarter_end")}},
        "metrics": {"type": "object", "additionalProperties": False,
                    "required": [m for m, _ in _METRICS],
                    "properties": {m: {"type": "object", "additionalProperties": False,
                                       "required": ["current", "previous_quarter", "year_ago_quarter", "evidence_id", "unit"],
                                       "properties": {k: _STR for k in
                                                      ("current", "previous_quarter", "year_ago_quarter", "evidence_id", "unit")}}
                                   for m, _ in _METRICS}},
    },
}

SYSTEM_PROMPT = """You read ONE company's quarterly results statement and extract four headline numbers.
Rules:
1. Use ONLY the <statement> passages supplied. Do not use outside knowledge or memory of the company.
2. The statement has columns for three-month (quarter) periods. Identify the current quarter, the immediately
   preceding quarter, and the same quarter a year earlier, by their period-end dates (YYYY-MM-DD).
3. For each of Revenue (revenue from operations / total revenue / interest earned for a bank), EBITDA, PBT
   (profit before tax), and PAT (profit for the period / profit after tax / net profit), give the value in
   each of those three quarter columns, copied VERBATIM exactly as printed (keep commas and decimals, e.g.
   "30,246" or "23,063.32"). Use the quarter columns only — never the year-to-date / full-year columns.
4. EBITDA: give it ONLY if a line is explicitly labelled EBITDA. Never compute or estimate it; otherwise null.
5. If a metric or a column value is not clearly present, use an empty string "". Never guess a number. Put the
   passage id the numbers came from in evidence_id. Set basis to "standalone" or "consolidated" if the heading
   says so, else "". Dates must be ISO (YYYY-MM-DD)."""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "")


def select_pnl_passages(passages: List[Dict[str, Any]], anchors: int = 1, max_passages: int = 8) -> List[Dict[str, Any]]:
    """One dated statement page from one filing, including all same-page chunks.

    Pages with only depreciation/finance-cost notes are not P&L statements. The
    latest supported quarter wins, then the strongest headline-row coverage. A
    second filing or a standalone page is never silently mixed into the packet.
    """
    pages: Dict[Tuple[Any, Any], List[Dict[str, Any]]] = {}
    for p in passages:
        if p.get("doc_type") == "exchange_filing":
            pages.setdefault((p.get("version_id"), p.get("page_index")), []).append(p)
    scored = []
    for key, group in pages.items():
        text = "\n".join(p.get("text") or "" for p in group)
        labels = sum(bool(re.search(pat, text, re.I)) for pat in _LABELS.values())
        if not labels or not _QUARTER.search(text):
            continue
        dates = [d for d in _statement_dates(text) if _quarter_end(d)]
        if not dates:
            continue
        score = labels * 10 + (3 if re.search(r"\bconsolidated\b", text, re.I) else 0)
        scored.append((max(dates), score, key))
    if not scored:
        return []
    _, _, winner = max(scored, key=lambda x: (x[0], x[1]))
    return pages[winner][:max_passages]


def _num(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    s = text.strip()
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[(),₹$]|rs\.?|inr|usd", "", s, flags=re.I).strip()
    try:
        v = float(s)
    except ValueError:
        return None
    return (-v if neg else v) if math.isfinite(v) else None


def _verbatim(value: Optional[str], passage_text: str) -> bool:
    if not value:
        return False
    # A substring such as 246 inside 30,246 is not a disclosed value. Preserve
    # commas, decimals and negative parentheses exactly as extracted.
    return _norm(value).strip() in {m.group(0) for m in _TOKEN.finditer(_norm(passage_text))}


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s.strip())
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    except (ValueError, AttributeError):
        return None


def _months_between(a: date, b: date) -> int:
    return (a.year - b.year) * 12 + (a.month - b.month)


def _quarter_label(d: Optional[date]) -> Optional[str]:
    if not d:
        return None
    # Indian fiscal year ends 31 March; Q1=Apr-Jun … Q4=Jan-Mar.
    q = {1: 4, 2: 4, 3: 4, 4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3}[d.month]
    end_year = d.year + 1 if d.month >= 4 else d.year
    return f"Q{q} FY{end_year - 1}-{str(end_year)[-2:]}"


def _pct(cur: float, base: float) -> Optional[float]:
    return round((cur - base) / abs(base) * 100, 1) if base else None


def _quarter_end(d: date) -> bool:
    return d.month in (3, 6, 9, 12) and d.day == calendar.monthrange(d.year, d.month)[1]


def _statement_dates(text: str) -> List[date]:
    """Read printed numeric, worded, and transposed table-header dates."""
    found: List[date] = []
    def add(y, m, d):
        try:
            value = date(int(y), int(m), int(d))
            if value not in found:
                found.append(value)
        except (ValueError, TypeError):
            pass
    for m in re.finditer(r"(?<!\d)(\d{1,2})[/.\-](\d{1,2})[/.\-](20\d{2})(?!\d)", text):
        add(m[3], m[2], m[1])
    for m in re.finditer(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)", text):
        add(m[1], m[2], m[3])
    for m in re.finditer(r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s*(" + _MONTH + r")\s*,?\s*(20\d{2})\b", text, re.I):
        add(m[3], _MONTH_NO[m[2][:3].lower()], m[1])
    for m in re.finditer(r"\b(" + _MONTH + r")\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(20\d{2})\b", text, re.I):
        add(m[3], _MONTH_NO[m[1][:3].lower()], m[2])
    lines = text.splitlines()
    for i, line in enumerate(lines[:-1]):
        heads = list(re.finditer(r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s*(" + _MONTH + r")\b", line, re.I))
        years = re.findall(r"\b20\d{2}\b", lines[i + 1])
        if len(heads) >= 2 and len(years) >= len(heads):
            for head, year in zip(heads, years):
                add(year, _MONTH_NO[head[2][:3].lower()], head[1])
    return found


def _row_texts(key: str, text: str) -> List[str]:
    """Bind figures to the named metric row, including numeric continuation rows."""
    out = []
    other = re.compile("|".join(p for k, p in _LABELS.items() if k != key), re.I)
    for match in re.finditer(_LABELS[key], text, re.I):
        start = text.rfind("\n", 0, match.start()) + 1
        prefix = text[start:match.start()]
        # Some PDFs put the three quarter values before the printed row label.
        numeric_prefix = len(list(_TOKEN.finditer(prefix))) >= 2 and not re.search(r"[A-Za-z]", prefix)
        line_end = text.find("\n", match.end())
        line_end = len(text) if line_end < 0 else line_end
        end = line_end
        for line in text[line_end + 1:].splitlines():
            if not line.strip() or (_TOKEN.search(line) and not re.search(r"[A-Za-z]", line)):
                end += len(line) + 1
            else:
                break
        row = text[start if numeric_prefix else match.end():end]
        next_metric = other.search(row)
        if next_metric:
            row = row[:next_metric.start()]
        out.append(row)
    return out


def _column_values(row: str, context: str) -> Dict[date, str]:
    """Associate printed period columns with row tokens for supported layouts only.

    Ordinary quarter-first statements can append full-year columns. Explicit
    segment tables can print one equal-width segment row per period, ending in
    the labelled Total column. Other column layouts are deliberately omitted.
    """
    dates = [d for d in _statement_dates(context) if _quarter_end(d)]
    # Remove row-calculation references such as (5-6+7), not negative amounts.
    clean = re.sub(r"\([^)]*\d\s*[-+*/=]\s*\d[^)]*\)", " ", row)
    values = [m.group(0) for m in _TOKEN.finditer(clean)]
    if not dates or not values:
        return {}
    quarter = _QUARTER.search(context)
    year = re.search(r"\byear\s+ended\b", context, re.I)
    if quarter is None or (year and year.start() < quarter.start()):
        return {}
    if len(values) == len(dates):
        return dict(zip(dates, values))
    if (re.search(r"business\s+segments|segment\s+reporting", context, re.I)
            and re.search(r"\bTotal\b", context) and len(values) % len(dates) == 0
            and len(values) > len(dates)):
        width = len(values) // len(dates)
        return dict(zip(dates, values[width - 1::width]))
    if year and len(dates) == 3 and len(values) == 5:
        return dict(zip(dates, values[:3]))
    return {}


def _unit(text: str) -> Tuple[Optional[str], Optional[str]]:
    m = re.search(r"(?:(₹|rs\.?|inr|rupees?|usd|us\$|\$|dollars?)\s*(?:in\s*)?)?(crores?|lakhs?|millions?|billions?)\b", text or "", re.I)
    if not m:
        return None, None
    currency = m[1]
    currency = ("INR" if currency and re.fullmatch(r"₹|rs\.?|inr|rupees?", currency, re.I)
                else "USD" if currency else None)
    return currency, m[2].lower().rstrip("s")


def _validated_unit(raw_unit: str, context: str) -> Tuple[Optional[str], Optional[str]]:
    currency, scale = _unit(context)
    requested_currency, requested_scale = _unit(raw_unit)
    if scale is None:
        return None, "no amount unit could be read from the cited statement page"
    if requested_scale and requested_scale != scale:
        return None, "the extracted unit conflicts with the statement page"
    if currency and requested_currency and currency != requested_currency:
        return None, "the extracted currency conflicts with the statement page"
    return (f"{'₹' if currency == 'INR' else 'USD'} {scale}" if currency
            else f"{scale} (currency not identified)"), None


def page_contexts(passages: List[Dict[str, Any]]) -> Dict[str, str]:
    pages: Dict[Tuple[Any, Any], List[str]] = {}
    for p in passages:
        pages.setdefault((p.get("version_id"), p.get("page_index")), []).append(p["text"])
    return {p["passage_id"]: "\n".join(pages[(p.get("version_id"), p.get("page_index"))]) for p in passages}


def _label_date(label: Optional[str]) -> Optional[str]:
    m = re.fullmatch(r"Q([1-4]) FY(\d{4})-(\d{2})", label or "")
    if not m:
        return None
    month = {1: 6, 2: 9, 3: 12, 4: 3}[int(m[1])]
    year = int(m[2]) + (1 if m[1] == "4" else 0)
    return date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def cached_extraction(result: Dict[str, Any]) -> Dict[str, Any]:
    """Reconstruct the recorded extraction for validation, without changing saved data."""
    cols = result.get("columns") or {}
    metrics = {m["key"]: {"current": (m.get("current") or {}).get("value_text"),
                          "previous_quarter": (m.get("previous_quarter") or {}).get("value_text"),
                          "year_ago_quarter": (m.get("year_ago_quarter") or {}).get("value_text"),
                          "unit": m.get("unit"), "evidence_id": m.get("evidence_id")}
               for m in result.get("metrics") or []}
    return {"basis": result.get("basis"), "metrics": metrics,
            "columns": {"current_quarter_end": cols.get("current_end") or _label_date(cols.get("current")),
                        "previous_quarter_end": cols.get("previous_end") or _label_date(cols.get("previous_quarter")),
                        "year_ago_quarter_end": cols.get("year_ago_end") or _label_date(cols.get("year_ago_quarter"))}}


def validate_and_compute(raw: Dict[str, Any], passages_by_id: Dict[str, str],
                         contexts: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Turn a model extraction into verified metrics with deterministic QoQ/YoY, or omit."""
    cols = raw.get("columns") or {}
    d_cur = _parse_date(cols.get("current_quarter_end"))
    d_prev = _parse_date(cols.get("previous_quarter_end"))
    d_yago = _parse_date(cols.get("year_ago_quarter_end"))
    # Exact quarter ends; invented but plausible dates are rejected per metric below.
    qoq_ok = bool(d_cur and d_prev and _quarter_end(d_cur) and _quarter_end(d_prev)
                  and _months_between(d_cur, d_prev) == 3)
    yoy_ok = bool(d_cur and d_yago and _quarter_end(d_cur) and _quarter_end(d_yago)
                  and d_cur.month == d_yago.month and d_cur.day == d_yago.day
                  and d_cur.year - d_yago.year == 1)

    contexts = contexts or passages_by_id
    metrics, omitted, warnings, bases = [], [], [], set()
    for key, label in _METRICS:
        m = (raw.get("metrics") or {}).get(key) or {}
        ptext = passages_by_id.get(m.get("evidence_id") or "", "")
        if not m.get("current") or not ptext:
            omitted.append({"metric": label, "reason": "no verified value in the selected statement" if key == "ebitda"
                            else "no cited current-quarter value was recorded"})
            continue
        context = contexts.get(m.get("evidence_id") or "", "")
        dates = _statement_dates(context)
        scopes = {s.lower() for s in re.findall(r"\b(standalone|consolidated)\b", context, re.I)}
        requested_basis = (raw.get("basis") or "").lower().strip()
        basis = next(iter(scopes)) if len(scopes) == 1 else None
        unit, unit_error = _validated_unit(m.get("unit") or "", context)
        reason = None
        if len(scopes) > 1:
            reason = "the statement page contains multiple reporting bases"
        elif basis and requested_basis and requested_basis != basis:
            reason = "the extracted reporting basis conflicts with the statement page"
        elif unit_error:
            reason = unit_error
        elif not _QUARTER.search(context) or not d_cur or d_cur not in dates or not _quarter_end(d_cur):
            reason = "the current quarter date is not supported by the statement page"
        rows = _row_texts(key, ptext)
        row = next((r for r in rows if _verbatim(m.get("current"), r)), "")
        if not row and reason is None:
            reason = "no exact current value could be bound to the named metric row"
        columns = _column_values(row, context)
        if not columns and reason is None:
            reason = "the printed period columns could not be associated with this metric row"
        if columns.get(d_cur) != m.get("current") and reason is None:
            reason = "the current value does not match its printed quarter column"
        cur_s = m.get("current") if not reason else None
        prev_s = m.get("previous_quarter") if (not reason and qoq_ok and d_prev in dates and columns.get(d_prev) == m.get("previous_quarter")) else None
        yago_s = m.get("year_ago_quarter") if (not reason and yoy_ok and d_yago in dates and columns.get(d_yago) == m.get("year_ago_quarter")) else None
        cur_v = _num(cur_s)
        if cur_v is None or (prev_s is None and yago_s is None):
            omitted.append({"metric": label, "reason": reason or ("no verified value in the selected statement" if key == "ebitda"
                            else "no verified current-quarter value with a comparable prior period")})
            continue
        prev_v, yago_v = _num(prev_s), _num(yago_s)
        metrics.append({
            "key": key, "label": label, "unit": unit, "basis": basis,
            "evidence_id": m.get("evidence_id"),
            "current": {"value_text": cur_s, "value": cur_v},
            "previous_quarter": {"value_text": prev_s, "value": prev_v} if prev_v is not None else None,
            "year_ago_quarter": {"value_text": yago_s, "value": yago_v} if yago_v is not None else None,
            "qoq_pct": _pct(cur_v, prev_v) if prev_v is not None else None,
            "yoy_pct": _pct(cur_v, yago_v) if yago_v is not None else None,
        })
        bases.add(basis)
        if basis is None:
            warnings.append("Reporting basis is not explicitly identified on the cited statement page.")
        if "currency not identified" in (unit or ""):
            warnings.append("The source states the amount scale, but its currency could not be verified from the cited page.")

    return {
        "basis": next(iter(bases)) if len(bases) == 1 else None,
        "columns": {"current": _quarter_label(d_cur), "previous_quarter": _quarter_label(d_prev),
                    "year_ago_quarter": _quarter_label(d_yago),
                    "current_end": d_cur.isoformat() if d_cur else None,
                    "previous_end": d_prev.isoformat() if d_prev else None,
                    "year_ago_end": d_yago.isoformat() if d_yago else None},
        "metrics": metrics, "omitted": omitted,
        "warnings": list(dict.fromkeys(warnings)), "validation_version": VALIDATION_VERSION,
        "gates": {"qoq_comparable": any(m["previous_quarter"] for m in metrics),
                  "yoy_comparable": any(m["year_ago_quarter"] for m in metrics)},
    }
