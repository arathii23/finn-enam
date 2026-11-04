"""Bounded passage retrieval over the eligible corpus only (FTS5 + fixed vocabulary).

Annual-report context and transcript commentary are retrieved separately so one document
type cannot crowd out the other. Limits are initial values, not recall guarantees."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from .db import Store

SECTION_VOCAB: Dict[str, Dict] = {
    "business_context": {
        "doc_types": ["annual_report"],
        "terms": ["business", "clients", "services", "offerings", "segments", "industry verticals", "strategy",
                  "digital", "revenue", "employees", "geographies", "we are", "our company", "overview",
                  "principal business", "manufacturing", "products and services", "product mix", "business model"],
        "limit": 4,
    },
    "management_commentary": {
        "doc_types": ["earnings_call_transcript"],
        "terms": ["guidance", "outlook", "demand", "margin", "large deals", "deal wins", "pipeline", "growth",
                  "constant currency", "discretionary", "expect", "environment", "clients"],
        "limit": 6,
    },
    "event_filing": {
        "doc_types": ["exchange_filing"],
        "terms": ["revenue", "growth", "guidance", "constant currency", "operating margin", "dividend",
                  "acquisition", "results", "quarter", "year ended"],
        "limit": 2,
    },
}
STOPWORDS = set("what does did the this that with from have has about which their there them they will would company is are was were and for into how why".split())
STOPWORDS.update("tell please explain show give given said say happened main current latest recent today yesterday understand information could should been being when where during much many also more than whom its our your management explicitly".split())
STOPWORDS.update("can you reason reasons cause causes detail details regarding related announcement announcements filing filings report reports reported update updates event events".split())
STOPWORDS.update("state states around context provide provided period periods".split())
# Search expansions name topics, never create company facts or financial values.
TERM_ALIASES = {
    "margin": ["margin", "margins"], "margins": ["margin", "margins"],
    "revenue": ["revenue", "revenues", "turnover"], "revenues": ["revenue", "revenues", "turnover"],
    "debt": ["debt", "borrowings", "loans", "leverage"],
    "cashflow": ["cash flow", "cash flows", "cashflow"],
    "guidance": ["guidance", "outlook", "forecast", "expect", "expectations"],
    "guided": ["guidance", "outlook", "forecast", "expect"],
    "assumptions": ["assumption", "assumptions", "assumes", "assuming", "subject to", "excluding"],
    "basis": ["basis", "assumptions", "assumes", "assuming", "headwinds", "tailwinds"],
    "conditions": ["condition", "conditions", "assuming", "subject to", "excluding"],
    "segments": ["segment", "segments"], "risks": ["risk", "risks"],
    "dividends": ["dividend", "dividends"], "profits": ["profit", "profits"],
    "resignation": ["resignation", "resigned", "resign"],
    "resign": ["resignation", "resigned", "resign"], "resigned": ["resignation", "resigned", "resign"],
    "auditor": ["auditor", "auditors"], "acquisitions": ["acquisition", "acquisitions"],
    "auditors": ["auditor", "auditors"],
    "director": ["director", "directors"], "directors": ["director", "directors"],
    "cfo": ["cfo", "chief financial officer"], "ceo": ["ceo", "chief executive officer"],
}
_CRITICAL_TOPICS = {"resignation", "resign", "resigned", "fraud", "litigation", "pledging"}
MAX_PASSAGE_CHARS = 1400
# Transcript referents ("below that 90 mark", "the target") are often defined one
# passage earlier by the same speaker. Pull a bounded same-speaker lead-in ONLY for
# passages that carry such a dangling referent, so the defining context is citable
# without inflating every packet.
CONTEXT_NEIGHBOURS = 1
MAX_CONTEXT_PER_SECTION = 2
# A number tied to a demonstrative/threshold word whose metric is likely stated earlier.
_DANGLING_REFERENT = re.compile(
    r"(below|above|that|the|this|reach|cross|around|near)\s+\w*\s*\d"
    r"|\b(mark|target|range|level|ratio|guidance)\b", re.I)
_FOLLOWING_QUALIFIER = re.compile(
    r"\b(however|but|subject to|provided|assuming|assumes?|exclud(?:e[sd]?|ing)|"
    r"includ(?:e[sd]?|ing)|caveat|barring|depends?|conditional|assumptions?|headwinds?|tailwinds?|offset)\b", re.I)


def _fts_query(terms: Sequence[str]) -> str:
    parts = []
    for t in terms:
        t = re.sub(r"[^A-Za-z0-9 ]", " ", t).strip().lower()
        if t:
            parts.append(f'"{t}"')
    return " OR ".join(parts)


def question_terms(question: Optional[str]) -> List[str]:
    if not question:
        return []
    words = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", question.lower())
    return [w for w in dict.fromkeys(words) if w not in STOPWORDS][:8]


def topic_matches(text: str, terms: Sequence[str]) -> int:
    """Whole-word topic overlap; a missing critical event must not match generic prose."""
    low = text.lower()
    def present(term):
        return any(re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low)
                   for alias in TERM_ALIASES.get(term, [term]))
    if any(t in _CRITICAL_TOPICS for t in terms):
        # An actor-specific question needs that actor AND event. A CFO/director
        # resignation is not evidence of an auditor resignation. Generic question
        # wording is removed by question_terms; explicit negative disclosures match.
        if any(not present(t) for t in terms):
            return 0
    return sum(present(t) for t in terms)



def _same_speaker_context(store: Store, version_id: str, page_index: int, seq: int,
                          speaker: Optional[str], have: set) -> List[Dict]:
    """Return up to CONTEXT_NEIGHBOURS passages immediately preceding (version order),
    by the same speaker, so a referent defined just before a cited line is in the packet."""
    if not speaker:
        return []
    rows = store.query(
        """SELECT passage_id, version_id, page_index, printed_page, speaker, text
           FROM passages
           WHERE version_id=?
             AND (page_index < ? OR (page_index = ? AND seq < ?))
           ORDER BY page_index DESC, seq DESC LIMIT ?""",
        (version_id, page_index, page_index, seq, CONTEXT_NEIGHBOURS),
    )
    out = []
    for r in rows:
        if (r.get("speaker") != speaker or r["page_index"] < page_index - 1
                or len((r["text"] or "").strip()) < 40):
            continue
        r["text"] = r["text"][:MAX_PASSAGE_CHARS]
        out.append(r)
    return out


def _following_qualification(store: Store, version_id: str, page_index: int, seq: int,
                             speaker: Optional[str]) -> Optional[Dict]:
    """Read the immediate next chunk, including short chunks topic search omits.

    Never jump over another speaker or across a distant page to find a qualifier.
    The chunk retains its own evidence ID; it is not spliced into the anchor.
    """
    if not speaker:
        return None
    rows = store.query(
        """SELECT passage_id, version_id, page_index, seq, printed_page, speaker, text
           FROM passages
           WHERE version_id=? AND (page_index > ? OR (page_index = ? AND seq > ?))
           ORDER BY page_index, seq LIMIT 1""",
        (version_id, page_index, page_index, seq),
    )
    if not rows:
        return None
    following = rows[0]
    text = (following.get("text") or "").strip()
    if (following.get("version_id") != version_id or following.get("speaker") != speaker
            or (following["page_index"], following.get("seq", 0)) <= (page_index, seq)
            or following["page_index"] > page_index + 1 or not text
            or not _FOLLOWING_QUALIFIER.search(text[:300])):
        return None
    following["text"] = following["text"][:MAX_PASSAGE_CHARS]
    return following


def retrieve_section(store: Store, section: str, versions: List[Dict], question: Optional[str] = None,
                     restrict_version_ids: Optional[List[str]] = None) -> List[Dict]:
    vocab = SECTION_VOCAB[section]
    pool = [v for v in versions if v["doc_type"] in vocab["doc_types"]]
    if restrict_version_ids is not None:
        pool = [v for v in pool if v["version_id"] in restrict_version_ids]
    if not pool:
        return []
    # newest first; the most recent document gets the larger share of the limit
    pool.sort(key=lambda v: v.get("published_at") or "", reverse=True)
    limit = vocab["limit"]
    terms = question_terms(question)
    if terms:
        # Search the actual question across a bounded history. Generic business vocabulary
        # must not outrank a debt/attrition/etc. question, or pretend an unsupported topic matched.
        pool = pool[:6]
        shares = [limit] * len(pool)
        query = _fts_query([a for t in terms for a in TERM_ALIASES.get(t, [t])])
    else:
        shares = [limit] if len(pool) == 1 else [limit - limit // 3] + [max(1, limit // 3)] + [0] * (len(pool) - 2)
        query = _fts_query(vocab["terms"])
    out: List[Dict] = []
    context_added = 0
    for version, share in zip(pool, shares):
        if share <= 0:
            continue
        sql = """SELECT p.passage_id, p.version_id, p.page_index, p.seq, p.printed_page, p.speaker, p.text,
                      bm25(passages_fts) AS score
               FROM passages_fts JOIN passages p ON p.passage_id = passages_fts.passage_id
               WHERE passages_fts MATCH ? AND passages_fts.version_id = ? AND length(p.text) >= 100
               ORDER BY score LIMIT 40"""
        rows = store.query(sql, (query, version["version_id"]))
        if section == "event_filing" and restrict_version_ids is not None and not terms:
            # A deliberate "read this filing" action is not a financial-keyword
            # search. Appointment, legal and other selected notices must be readable
            # too; take bounded opening passages with their original page locators.
            rows = store.query("SELECT passage_id, version_id, page_index, seq, printed_page, speaker, text, 0 AS score "
                               "FROM passages WHERE version_id=? AND length(text)>=40 ORDER BY page_index,seq LIMIT 12",
                               (version["version_id"],))
        per_page: Dict[int, int] = {}
        management_speakers = set((version.get("identification") or {}).get("management_speakers", []))
        if section == "business_context" and not terms:
            # A separate defining-activities query prevents dense generic
            # customer/governance prose crowding out a short business table.
            anchors = _fts_query(["principal business", "principal activities", "business activities", "business segments", "manufacture"])
            core = store.query(sql, (anchors, version["version_id"]))
            ids = {r["passage_id"] for r in core}
            rows = core + [r for r in rows if r["passage_id"] not in ids]
            # Governance/online-voting instructions share words such as
            # 'services' and 'company' but do not explain the operating business.
            irrelevant = re.compile(r"e[- ]?voting|evoting|shareholders?\s+(?:should|holding)|remuneration\s+committee|audit\s+evidence|ownership\s+interest", re.I)
            rows = [r for r in rows if not irrelevant.search(r["text"])]
            defining = re.compile(r"principal\s+(?:business|activit)|business\s+(?:activit|segments)", re.I)
            rows.sort(key=lambda r: not bool(defining.search(r["text"])))
        if terms:
            rows = [r for r in rows if topic_matches(r["text"], terms)]
            rows.sort(key=lambda r: (-topic_matches(r["text"], terms), r["score"]))
        selected_ids = {r["passage_id"] for r in out}

        def _enrich(rec):
            rec["text"] = rec["text"][:MAX_PASSAGE_CHARS]
            rec["doc_type"] = version["doc_type"]
            rec["period_label"] = version.get("period_label")
            rec["published_at"] = version.get("published_at")
            return rec

        for r in rows:
            if section == "management_commentary" and (r["speaker"] or "").lower() == "moderator":
                continue
            if section == "management_commentary" and r["speaker"] not in management_speakers:
                continue
            if per_page.get(r["page_index"], 0) >= 1:
                continue
            if r["passage_id"] in selected_ids:
                continue
            following = (_following_qualification(store, version["version_id"], r["page_index"], r["seq"], r["speaker"])
                         if section == "management_commentary" else None)
            if following and following["passage_id"] not in selected_ids and context_added >= MAX_CONTEXT_PER_SECTION:
                # Respect the packet bound by omitting an incomplete headline,
                # rather than displaying it without a known following condition.
                continue
            per_page[r["page_index"]] = per_page.get(r["page_index"], 0) + 1
            out.append(_enrich(r))
            selected_ids.add(r["passage_id"])
            if following:
                r.setdefault("_following_context_ids", []).append(following["passage_id"])
                r.setdefault("_context_ids", []).append(following["passage_id"])
                if following["passage_id"] not in selected_ids:
                    following["_context_for"] = r["passage_id"]
                    out.append(_enrich(following))
                    selected_ids.add(following["passage_id"])
                    context_added += 1
            if (section == "management_commentary" and context_added < MAX_CONTEXT_PER_SECTION
                    and _DANGLING_REFERENT.search(r["text"] or "")):
                for ctx in _same_speaker_context(store, version["version_id"], r["page_index"], r["seq"],
                                                 r["speaker"], selected_ids):
                    r.setdefault("_context_ids", []).append(ctx["passage_id"])
                    if ctx["passage_id"] not in selected_ids:
                        ctx["_context_for"] = r["passage_id"]
                        out.append(_enrich(ctx))
                        context_added += 1
                    selected_ids.add(ctx["passage_id"])
                    if context_added >= MAX_CONTEXT_PER_SECTION:
                        break
            if sum(per_page.values()) >= share:
                break
    if terms:
        # Rank anchors first, newest among equal topic matches. Retain the defining
        # lead-in with its anchor as a unit rather than letting a zero-overlap context
        # fall off the packet cap while its dangling numeric claim survives.
        by_id = {r["passage_id"]: r for r in out}
        anchors = [r for r in out if not r.get("_context_for")]
        anchors.sort(key=lambda r: r.get("published_at") or "", reverse=True)
        anchors.sort(key=lambda r: topic_matches(r["text"], terms), reverse=True)
        selected = anchors[:limit]
        keep_context = {pid for r in selected for pid in r.get("_context_ids", [])}
        selected_ids = {r["passage_id"] for r in selected}
        out = selected + [by_id[pid] for pid in sorted(keep_context) if pid in by_id and pid not in selected_ids]
    return out
