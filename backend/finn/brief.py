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
from .retrieval import SECTION_VOCAB, question_terms, topic_matches

# Keep each highlight to one idea plus its qualification; do not reproduce whole pages.
MAX_QUOTE_CHARS = 1800
MAX_HIGHLIGHTS = 6
# Sentence-ish split that keeps decimals, Rs. and common abbreviations intact.
_ABBR = r"(?<!\b[A-Z])(?<!\bRs)(?<!\bNo)(?<!\bMr)(?<!\bMs)(?<!\bQ[1-4])(?<!\bvs)(?<!\bFY)"
_SENT = re.compile(_ABBR + r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])")
_NUM = re.compile(r"\d")
# Conditions/qualifiers whose preceding or following sentence carries the real caveat.
_QUALIFIER = re.compile(r"\b(but|however|subject to|provided|expect|guidance|target|assuming|"
                        r"excluding|including|caveat|barring|depend|assumptions?|assumes?|offset|headwinds?|tailwinds?)\b", re.I)
# Call-opening greetings and hand-overs are transcript boilerplate, not evidence. A quote is
# dropped only when it STARTS with such a phrase, so substantive sentences are unaffected.
_PLEASANTRY = re.compile(
    r"^\W*(welcome\b|good\s+(?:morning|afternoon|evening)\b|(?:thank\s+you|thanks)\s+(?:all\s+)?for\s+joining\b|"
    r"(?:i|we)\s+(?:now\s+)?(?:would\s+like\s+to\s+)?(?:hand|turn)\s+(?:it\s+|the\s+(?:call|floor|conference)\s+)?over\b|"
    r"over\s+to\s+you\b)", re.I)
_SECTION_ORDER = ["event_filing", "business_context", "management_commentary"]
_SECTION_LABEL = {"event_filing": "exchange filing", "business_context": "annual report",
                  "management_commentary": "earnings-call transcript"}


def _sentences(text: str) -> List[str]:
    parts = [s.strip() for s in _SENT.split((text or "").strip()) if s.strip()]
    return parts or ([text.strip()] if text and text.strip() else [])


def _score(sentence: str, terms: List[str], vocab: List[str], want_numbers: bool) -> int:
    low = sentence.lower()
    if terms:
        # A number or generic business word cannot turn an unrelated sentence into an answer.
        matches = topic_matches(sentence, terms)
        if not matches:
            return 0
        focus = (6 if {"guidance", "guided", "outlook", "forecast"}.intersection(terms)
                 and re.search(r"\b(guidance|outlook|forecast)\b", low) else 0)
        if {"basis", "assumptions", "conditions"}.intersection(terms) and re.search(
                r"\b(assumptions?|assumes?|assuming|subject to|headwinds?|tailwinds?|offset)\b", low):
            focus += 6
        return matches * 3 + focus
    score = 0
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
    score, best_i, best = max(scored, key=lambda x: (x[0], -x[1]))
    if terms and score <= 0:
        return None
    chosen = [best_i]
    # Keep a neighbour when the caveat lives next door: a condition in the best sentence
    # (look forward) or a dangling referent/pronoun start (look back).
    if best_i + 1 < len(sents) and (_QUALIFIER.search(best) or _QUALIFIER.search(sents[best_i + 1])):
        chosen.append(best_i + 1)
        if best_i + 2 < len(sents) and _QUALIFIER.search(sents[best_i + 2]):
            chosen.append(best_i + 2)
    if best_i > 0 and (re.match(r"^(this|that|these|those|it|they|he|she|however|but)\b", best, re.I)
                       or _QUALIFIER.search(sents[best_i - 1])):
        chosen.insert(0, best_i - 1)
    valid = [i for i in sorted(set(chosen)) if spans[i]]
    if not valid:
        return None
    start, end = min(spans[i][0] for i in valid), max(spans[i][1] for i in valid)
    quote = src[start:end].strip()
    if len(quote) > MAX_QUOTE_CHARS:
        # Abstain rather than cutting a sentence/condition or dropping its neighbour.
        return None
    return quote or None


def build_source_brief(sections: Dict[str, List[Dict]], question: Optional[str]) -> SourceBrief:
    """Build the extractive brief from already-retrieved, ranked passages (no DB, no model)."""
    terms = question_terms(question)
    highlights: List[BriefItem] = []
    doc_counts: Dict[str, int] = {}
    seen = set()
    quoted_sources = []
    # "management" is a search stopword, but asking what management said is a request for
    # management's own statements first, not for an annual-report note that shares a keyword.
    asked_management = bool(re.search(r"\b(management|said|says?|told|commentary|ceo|cfo)\b", (question or "").lower()))
    management_focus = asked_management or bool(
        {"guidance", "guided", "outlook", "forecast", "assumptions", "conditions", "demand"}.intersection(terms))
    section_order = (["management_commentary", "business_context", "event_filing"] if management_focus else _SECTION_ORDER)
    for name in section_order:
        passages = sections.get(name) or []
        by_id = {p["passage_id"]: p for p in passages}
        context_ids = {pid for p in passages for pid in p.get("_context_ids", p.get("_following_context_ids", []))}
        vocab = SECTION_VOCAB.get(name, {}).get("terms", [])
        want_numbers = name in ("management_commentary", "event_filing")
        added = 0
        section_limit = 3 if name == "management_commentary" else (1 if management_focus else 2)
        candidates = []
        for p in passages:
            if p["passage_id"] in context_ids or p.get("_context_for"):
                continue  # context is shown with its anchor, never as an incomplete standalone answer
            quote = _select_quote(p.get("text") or "", terms, vocab, want_numbers)
            if quote and not _PLEASANTRY.match(quote):
                candidates.append((p, quote))
        if terms:
            # Rank the selected statement, not the entire surrounding passage.
            # A dense results paragraph must not outrank a direct guidance answer.
            candidates.sort(key=lambda item: item[0].get("published_at") or "", reverse=True)
            candidates.sort(key=lambda item: _score(item[1], terms, vocab, want_numbers), reverse=True)
        for p, quote in candidates:
            if not quote or quote in seen:
                continue
            # A bundled media/analyst call can repeat the same guidance with tiny
            # transcription differences. Retain one exact quote, never merge or
            # paraphrase. Different figures, speakers or qualifications survive.
            words = set(re.findall(r"[a-z]+", quote.lower()))
            signature = (re.findall(r"\d+(?:\.\d+)?", quote), set(_QUALIFIER.findall(quote.lower())))
            if p.get("version_id") and any(
                    p["version_id"] == prev.get("version_id") and p.get("speaker") == prev.get("speaker")
                    and signature == old_signature and len(words & old_words) / max(1, len(words | old_words)) >= 0.82
                    for prev, old_words, old_signature in quoted_sources):
                continue
            group = [(p, quote)]
            following_ids = p.get("_following_context_ids", [])
            preceding_ids = [pid for pid in p.get("_context_ids", []) if pid not in following_ids]
            if preceding_ids:
                # A page break may split one sentence between a leading context
                # chunk and the anchor. Keep both complete source slices in order,
                # rather than selecting away the sentence's continuation.
                preceding = [by_id.get(pid) for pid in preceding_ids]
                if any(ctx is None or ctx.get("speaker") != p.get("speaker")
                       or ctx.get("version_id") != p.get("version_id") for ctx in preceding):
                    continue
                ordered = sorted(preceding, key=lambda ctx: (ctx["page_index"], ctx.get("seq", 0)))
                group = [(ctx, (ctx.get("text") or "").strip()) for ctx in ordered] + [(p, (p.get("text") or "").strip())]
                if any(not fragment or len(fragment) > MAX_QUOTE_CHARS for _, fragment in group):
                    continue
            for pid in following_ids:
                ctx = by_id.get(pid)
                if (ctx is None or ctx.get("speaker") != p.get("speaker")
                        or ctx.get("version_id") != p.get("version_id")):
                    group = []
                    break
                # Preserve the complete adjacent qualification as its OWN exact
                # passage slice and citation. Do not select only a topical sentence
                # or claim that text spliced across two passages is one quote.
                condition = (ctx.get("text") or "").strip()
                if not condition or len(condition) > MAX_QUOTE_CHARS:
                    group = []
                    break
                group.append((ctx, condition))
            if not group or added + len(group) > section_limit or len(highlights) + len(group) > MAX_HIGHLIGHTS:
                continue  # A known condition and headline fit together, or neither is shown.
            for source, fragment in group:
                seen.add(fragment)
                quoted_sources.append((source, set(re.findall(r"[a-z]+", fragment.lower())),
                                       (re.findall(r"\d+(?:\.\d+)?", fragment), set(_QUALIFIER.findall(fragment.lower())))))
                highlights.append(BriefItem(
                    kind=name, quote=fragment, speaker=source.get("speaker"),
                    doc_type=source.get("doc_type") or "", period_label=source.get("period_label"),
                    evidence_id=source["passage_id"], page_index=source["page_index"],
                    context_evidence_ids=[item["passage_id"] for item, _ in group] if len(group) > 1 else []))
                doc_counts[source.get("doc_type") or ""] = doc_counts.get(source.get("doc_type") or "", 0) + 1
                added += 1
            if added >= section_limit or len(highlights) >= MAX_HIGHLIGHTS:
                break
        if len(highlights) >= MAX_HIGHLIGHTS:
            break

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
