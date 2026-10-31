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
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", question.lower())
    return [w for w in dict.fromkeys(words) if w not in STOPWORDS][:8]



def _same_speaker_context(store: Store, version_id: str, page_index: int, seq: int,
                          speaker: Optional[str], have: set) -> List[Dict]:
    """Return up to CONTEXT_NEIGHBOURS passages immediately preceding (version order),
    by the same speaker, so a referent defined just before a cited line is in the packet."""
    if not speaker:
        return []
    rows = store.query(
        """SELECT passage_id, version_id, page_index, printed_page, speaker, text
           FROM passages
           WHERE version_id=? AND speaker=?
             AND (page_index < ? OR (page_index = ? AND seq < ?))
           ORDER BY page_index DESC, seq DESC LIMIT ?""",
        (version_id, speaker, page_index, page_index, seq, CONTEXT_NEIGHBOURS),
    )
    out = []
    for r in rows:
        if r["passage_id"] in have or len((r["text"] or "").strip()) < 40:
            continue
        r["text"] = r["text"][:MAX_PASSAGE_CHARS]
        out.append(r)
    return out

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
    shares = [limit] if len(pool) == 1 else [limit - limit // 3] + [max(1, limit // 3)] + [0] * (len(pool) - 2)
    query = _fts_query(list(vocab["terms"]) + question_terms(question))
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
        per_page: Dict[int, int] = {}
        management_speakers = set((version.get("identification") or {}).get("management_speakers", []))
        if section == "business_context":
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
            per_page[r["page_index"]] = per_page.get(r["page_index"], 0) + 1
            out.append(_enrich(r))
            selected_ids.add(r["passage_id"])
            if (section == "management_commentary" and context_added < MAX_CONTEXT_PER_SECTION
                    and _DANGLING_REFERENT.search(r["text"] or "")):
                for ctx in _same_speaker_context(store, version["version_id"], r["page_index"], r["seq"],
                                                 r["speaker"], selected_ids):
                    out.append(_enrich(ctx))
                    selected_ids.add(ctx["passage_id"])
                    context_added += 1
                    if context_added >= MAX_CONTEXT_PER_SECTION:
                        break
            if sum(per_page.values()) >= share:
                break
    return out
