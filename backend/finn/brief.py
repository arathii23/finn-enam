"""Deterministic, query-aware extractive source brief — built with NO model call.

When no model is configured (the shipped default), a research job still returns something an
analyst can use: the single most relevant verbatim sentence(s) from each eligible primary
source, labelled with document, period and speaker, and linked to exact evidence. This is the
honest keyless floor — it selects and quotes primary text, it never synthesises a new claim,
computes a figure, or writes from memory. A sentence is lifted exactly as printed; the only
transformation is choosing which sentences matter for the question and trimming length.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from .contracts import BriefItem, SourceBrief
from .retrieval import SECTION_VOCAB, question_terms

# Keep each highlight to one idea plus its qualification; do not reproduce whole pages.
MAX_QUOTE_CHARS = 360
# Sentence-ish split that keeps decimals, Rs. and common abbreviations intact.
_ABBR = r"(?<!\b[A-Z])(?<!\bRs)(?<!\bNo)(?<!\bMr)(?<!\bMs)(?<!\bQ[1-4])(?<!\bvs)(?<!\bFY)"
_SENT = re.compile(_ABBR + r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])")
_NUM = re.compile(r"\d")
# Conditions/qualifiers whose preceding or following sentence carries the real caveat.
_QUALIFIER = re.compile(r"\b(but|however|subject to|provided|expect|guidance|target|assuming|"
                        r"excluding|including|caveat|barring|depend)\b", re.I)
_SECTION_ORDER = ["event_filing", "business_context", "management_commentary"]
_SECTION_LABEL = {"event_filing": "exchange filing", "business_context": "annual report",
                  "management_commentary": "earnings-call transcript"}


def _sentences(text: str) -> List[str]:
    parts = [s.strip() for s in _SENT.split((text or "").strip()) if s.strip()]
    return parts or ([text.strip()] if text and text.strip() else [])


def _score(sentence: str, terms: List[str], vocab: List[str], want_numbers: bool) -> int:
    low = sentence.lower()
    score = sum(3 for t in terms if t in low)
    score += sum(1 for t in vocab if t in low)
    if want_numbers and _NUM.search(sentence):
        score += 1
    return score


def _select_quote(text: str, terms: List[str], vocab: List[str], want_numbers: bool) -> Optional[str]:
    """Pick the best sentence for the question, keep its adjacent qualifier, and return it as
    an EXACT slice of the source so the quote is always verbatim (original whitespace and all)."""
    src = text or ""
    sents = _sentences(src)
    if not sents:
        return None
    # Locate each sentence's span in the source; quoting a literal slice keeps it verbatim.
    spans: List[Optional[tuple]] = []
    cursor = 0
    for s in sents:
        idx = src.find(s, cursor)
        if idx < 0:
            idx = src.find(s)
        spans.append((idx, idx + len(s)) if idx >= 0 else None)
        if idx >= 0:
            cursor = idx + len(s)
    scored = [(_score(s, terms, vocab, want_numbers), i, s) for i, s in enumerate(sents)]
    _, best_i, best = max(scored, key=lambda x: (x[0], -x[1]))
    chosen = [best_i]
    # Keep a neighbour when the caveat lives next door: a condition in the best sentence
    # (look forward) or a dangling referent/pronoun start (look back).
    if _QUALIFIER.search(best) and best_i + 1 < len(sents):
        chosen.append(best_i + 1)
    if re.match(r"^(this|that|these|those|it|they|he|she)\b", best, re.I) and best_i - 1 >= 0:
        chosen.insert(0, best_i - 1)
    valid = [i for i in sorted(set(chosen)) if spans[i]]
    if not valid:
        return None
    start, end = min(spans[i][0] for i in valid), max(spans[i][1] for i in valid)
    quote = src[start:end].strip()
    if len(quote) > MAX_QUOTE_CHARS:
        bs = spans[best_i]
        quote = src[bs[0]:bs[1]].strip() if bs else quote
        if len(quote) > MAX_QUOTE_CHARS:
            quote = quote[:MAX_QUOTE_CHARS].rsplit(" ", 1)[0] + "…"
    return quote or None


def build_source_brief(sections: Dict[str, List[Dict]], question: Optional[str]) -> SourceBrief:
    """Build the extractive brief from already-retrieved, ranked passages (no DB, no model)."""
    terms = question_terms(question)
    highlights: List[BriefItem] = []
    doc_counts: Dict[str, int] = {}
    for name in _SECTION_ORDER:
        passages = sections.get(name) or []
        vocab = SECTION_VOCAB.get(name, {}).get("terms", [])
        want_numbers = name in ("management_commentary", "event_filing")
        for p in passages:
            quote = _select_quote(p.get("text") or "", terms, vocab, want_numbers)
            if not quote:
                continue
            highlights.append(BriefItem(
                kind=name, quote=quote, speaker=p.get("speaker"),
                doc_type=p.get("doc_type") or "", period_label=p.get("period_label"),
                evidence_id=p["passage_id"], page_index=p["page_index"]))
            doc_counts[p.get("doc_type") or ""] = doc_counts.get(p.get("doc_type") or "", 0) + 1

    if not highlights:
        return SourceBrief(status="empty", query_terms=terms,
                           headline="No eligible primary-source passage matched this request.")

    pieces = []
    for dt, label in (("annual_report", "annual report"), ("earnings_call_transcript", "transcript"),
                      ("exchange_filing", "exchange filing")):
        n = doc_counts.get(dt, 0)
        if n:
            pieces.append(f"{n} {label}{'s' if n != 1 else ''} extract{'s' if n != 1 else ''}")
    focus = f" selected for: {', '.join(terms)}" if terms else ""
    headline = f"{', '.join(pieces)}{focus}."
    return SourceBrief(status="extractive", headline=headline, query_terms=terms,
                       highlights=highlights, suggested_questions=_suggest(sections, highlights))


def _suggest(sections: Dict[str, List[Dict]], highlights: List[BriefItem]) -> List[str]:
    """Deterministic next questions that will change retrieval — no model, no fabrication.

    Each suggestion is only offered when the corpus can actually answer it (the relevant
    document type is present), so a tap re-runs retrieval against real evidence."""
    have = {h.kind for h in highlights}
    out: List[str] = []
    if "management_commentary" in have:
        out.append("What guidance did management give on growth and margins?")
    if "business_context" in have:
        out.append("What are the company's main business segments and revenue mix?")
    if sections.get("event_filing"):
        out.append("What are the headline numbers in the latest results filing?")
    if "management_commentary" in have:
        out.append("What demand or deal commentary did management share this quarter?")
    return out[:3]
