"""Versioned primary documents: fetch, identify, prove publication availability, and
extract page-located passages. Rules here are generic, never company-specific."""
from __future__ import annotations

import io
import json
import re
from collections import Counter
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from pypdf import PdfReader

from ..config import IST, PARSER_VERSION
from ..contracts import AvailabilityEvidence, Company
from ..db import Store, sha256_bytes, utcnow
from .fetch import Fetcher
from . import nse

TYPE_TERMS = {
    "annual_report": ["annual report", "integrated annual report", "integrated report"],
    "earnings_call_transcript": ["earnings call", "conference call", "transcript", "earnings conference"],
    "exchange_filing": ["board meeting", "outcome", "financial results", "intimation", "regulation 30"],
}
SPEAKER_RE = re.compile(r"^\s*([A-Z][A-Za-z.'\-]+(?: [A-Z][A-Za-z.'\-]+){0,4})\s*:\s+", re.M)
CHUNK_CHARS = 1400
NAME_LINE_RE = re.compile(r"[A-Z][A-Za-z.'\-]+(?:[ \t]+[A-Z][A-Za-z.'\-]+){1,4}")
ROLE_WORDS = {"chief", "officer", "head", "executive", "director", "financial", "corporate",
              "participants", "analysts", "journalists", "conference", "call", "external", "document",
              "limited", "report", "relations", "president", "controller", "registered", "regd.",
              "office", "scrip", "code", "id", "email", "website", "page", "company", "secretary",
              "bank", "stock", "exchange", "earnings", "investor", "management",
              "dear", "sir", "madam", "subject", "reference", "ref", "encl"}
HONORIFIC_RE = re.compile(r"^(?:mr|mrs|ms|dr)\.?\s+", re.I)
ROSTER_NAME_ROLE_RE = re.compile(
    r"\b(?:MR|MRS|MS|DR)\.?\s+"
    r"([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){1,4})\s*[-–—]",
    re.I,
)


def _person_name(value: str) -> bool:
    value = HONORIFIC_RE.sub("", value.strip())
    return (not value.isupper() and bool(NAME_LINE_RE.fullmatch(value))
            and not (set(value.lower().split()) & ROLE_WORDS))


def _person_label(value: str) -> bool:
    """Colon-labelled dialogue may use uppercase names; headings remain excluded."""
    value = HONORIFIC_RE.sub("", value.strip())
    return _person_name(value.title() if value.isupper() else value)


def _name_key(value: str) -> str:
    return re.sub(r"\s+", " ", HONORIFIC_RE.sub("", value.strip())).casefold()


def transcript_speakers(pages: List[str]) -> Tuple[set, set]:
    """Conservative standalone labels and names listed in management rosters.

    Several publishers put speaker names on their own line without a colon.
    Repetition supports a label; a participant heading is never a person's name.
    """
    names: Counter = Counter()
    roster_names = set()
    dialogue = {}
    in_management = False
    for text in pages:
        # Preserve dialogue spelling while allowing an uppercase/honorific roster
        # to resolve to the same person. Mere mentions do not establish speakers.
        normalized = re.sub(r"[ \t]+", " ", text)
        for match in SPEAKER_RE.finditer(normalized):
            label = match.group(1).strip()
            if _person_label(label):
                dialogue.setdefault(_name_key(label), label)
        for raw in text.splitlines():
            line = re.sub(r"[ \t]+", " ", raw).strip().rstrip(":")
            if line.upper() in ("CORPORATE PARTICIPANTS", "MANAGEMENT", "MANAGEMENT PARTICIPANTS"):
                in_management = True
                continue
            if line.upper() in ("ANALYSTS", "JOURNALISTS", "ANALYST PARTICIPANTS", "CONFERENCE CALL PARTICIPANTS"):
                in_management = False
                continue
            if _person_name(line):
                names[line] += 1
                if in_management:
                    roster_names.add(line)
            if line.lower() == "moderator" or re.match(r"^[A-Za-z .'-]+:\s+", line):
                in_management = False

        # Common exchange bundles declare participants inline with honorifics and
        # roles, rather than one title-case name per line. Bound the roster to its
        # page and stop before analyst lists or actual moderated dialogue.
        for heading in re.finditer(
            r"(?im)^[ \t]*(?:CORPORATE PARTICIPANTS|MANAGEMENT(?: PARTICIPANTS)?)(?:[ \t]*:[ \t]*|[ \t]*$)", normalized
        ):
            block = normalized[heading.end():heading.end() + 2500]
            stop = re.search(r"(?im)^[ \t]*(?:ANALYSTS|JOURNALISTS|ANALYST PARTICIPANTS|Moderator\s*:)", block)
            if stop:
                block = block[:stop.start()]
            roster_names.update(re.sub(r"\s+", " ", m.group(1)).strip()
                                for m in ROSTER_NAME_ROLE_RE.finditer(block))

        # Some calls introduce the management team in prose. Require an explicit
        # team declaration and a name-to-role delimiter; a moderator introducing
        # an analyst or an incidental executive mention is insufficient.
        for declaration in re.finditer(
            r"(?i)\bmanagement\s+team\s+(?:comprising|consisting\s+of|including)\b", normalized
        ):
            block = normalized[declaration.end():declaration.end() + 700]
            stop = re.search(r"(?i)\b(?:we will start|we'll start|opening remarks|q&a)\b|Moderator\s*:", block)
            if stop:
                block = block[:stop.start()]
            roster_names.update(re.sub(r"\s+", " ", m.group(1)).strip()
                                for m in ROSTER_NAME_ROLE_RE.finditer(block))

    standalone = {name for name, count in names.items() if count >= 2}
    canonical = {_name_key(name): name for name in standalone}
    canonical.update(dialogue)
    management = {canonical[_name_key(name)] for name in roster_names
                  if _person_label(name) and _name_key(name) in canonical}
    return standalone | set(dialogue.values()) | {"Moderator"}, management


# ---------------------------------------------------------------- identification
def fiscal_period_terms(period_start: Optional[str], period_end: Optional[str]) -> List[str]:
    """Generic Indian fiscal-year spellings for a period ending in a given year."""
    if not period_end:
        return []
    end = date.fromisoformat(period_end)
    fy_end = end.year if end.month <= 3 else end.year + 1
    a, b = fy_end - 1, fy_end
    yy = str(b)[2:]
    return [
        f"{a}-{yy}", f"{a}–{yy}", f"{a}-{b}", f"{a}–{b}", f"{a} -{yy}", f"{a}-{str(b)}",
        f"fy{yy}", f"fy {yy}", f"fy{b}", f"fy {b}", f"fy'{yy}", f"fiscal {b}", f"fiscal year {b}",
        f"financial year {a}-{yy}", f"march 31, {b}", f"31 march {b}", f"31st march {b}",
    ]


def company_name_terms(legal_name: str) -> List[str]:
    base = re.sub(r"\b(limited|ltd\.?|private|pvt\.?)\b", "", legal_name, flags=re.I)
    base = re.sub(r"\s+", " ", base).strip(" .,").lower()
    terms = [legal_name.lower(), base]
    first = base.split(" ")[0] if base else ""
    if len(first) >= 5:
        terms.append(first)
    return [t for t in dict.fromkeys(terms) if t]


def identify_document(pages: List[str], company: Company, doc_type: str,
                      period_start: Optional[str], period_end: Optional[str]) -> Dict[str, Any]:
    head = " ".join(pages[:6]).lower()
    head = re.sub(r"\s+", " ", head)
    name_hits = [t for t in company_name_terms(company.legal_name) if t in head]
    type_hits = [t for t in TYPE_TERMS.get(doc_type, []) if t in head]
    period_terms = fiscal_period_terms(period_start, period_end)
    period_hits = [t for t in period_terms if t in head]
    period_required = doc_type in ("annual_report", "earnings_call_transcript") and bool(period_terms)
    ok = bool(name_hits) and bool(type_hits) and (bool(period_hits) or not period_required)
    return {
        "identity_ok": ok,
        "company_terms_found": name_hits,
        "type_terms_found": type_hits,
        "period_terms_found": period_hits,
        "period_required": period_required,
        "pages_checked": min(6, len(pages)),
        "method": "text match on first pages (generic rules)",
    }


# ---------------------------------------------------------------- extraction
def infer_reporting_period(pages: List[str], doc_type: str) -> Dict[str, Any]:
    """Read an explicit header period; never derive it from a file/call date."""
    headers = "\n".join(p[:2500] for p in pages[:2]).replace("’", "'").replace("–", "-")
    if doc_type == "earnings_call_transcript":
        found = re.findall(r"\bQ([1-4])\s*(&\s*9M\s*)?FY\s*'?\s*(20\d{2}|\d{2})(?:\s*[-/]\s*(20\d{2}|\d{2}))?\b", headers, re.I)
        periods = set()
        for quarter, ytd, first, last in found:
            end_year = int(last or first)
            if end_year < 100:
                end_year += 2000
            periods.add((int(quarter), end_year))
        if len(periods) != 1:
            return {"period_inference": "ambiguous" if periods else "not identified from title/header"}
        q, fy_end = periods.pop()
        with_ytd = any(bool(ytd) for _, ytd, _, _ in found)
        scope = f"Q{q} & 9M" if with_ytd else f"Q{q}"
        return {"period_label": f"{scope} FY{fy_end-1}-{str(fy_end)[-2:]}",
                "period_scope": "quarter and nine months" if with_ytd else "quarter",
                "period_inference": "explicit Q/FY title/header; exact calendar dates not inferred"}
    if doc_type == "annual_report":
        found = re.findall(r"(?:annual\s+report|integrated\s+report)[\s\S]{0,60}?\b(20\d{2})\s*-\s*(20\d{2}|\d{2})\b", headers, re.I)
        periods = {(int(a), int(b) if len(b) == 4 else 2000 + int(b)) for a, b in found}
        periods = {(a, b) for a, b in periods if b == a + 1}
        if len(periods) == 1:
            a, b = periods.pop()
            return {"period_label": f"FY{a}-{str(b)[-2:]}",
                    "period_inference": "explicit annual-report title/header; exact calendar dates not inferred"}
    return {"period_inference": "not identified from title/header"}


def extract_pages(data: bytes, max_pages: int) -> Tuple[List[str], int, str]:
    reader = PdfReader(io.BytesIO(data))
    total = len(reader.pages)
    texts: List[str] = []
    for i, page in enumerate(reader.pages):
        if i >= max_pages:
            break
        try:
            texts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - a single bad page must not sink the document
            texts.append("")
    nonempty = sum(1 for t in texts if len(t.strip()) > 30)
    if nonempty == 0:
        status = "failed"
    elif total > max_pages or nonempty < 0.6 * len(texts):
        status = "partial"
    else:
        status = "extracted"
    return texts, total, status


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_page(text: str, speaker_aware: bool, carry_speaker: Optional[str],
               known_speakers: Optional[set] = None) -> Tuple[List[Tuple[str, Optional[str]]], Optional[str]]:
    """Split one page into (text, speaker) passages. Speaker labels carry across pages."""
    text = _clean(text)
    if not text:
        return [], carry_speaker
    segments: List[Tuple[str, Optional[str]]] = []
    if speaker_aware:
        roster = bool(re.search(r"(?im)^[ \t]*(?:CORPORATE PARTICIPANTS|MANAGEMENT|ANALYSTS|JOURNALISTS)[ \t]*:?[ \t]*$", text))
        if roster:
            carry_speaker = None
        matches = [(m.start(), m.group(1).strip()) for m in SPEAKER_RE.finditer(text)
                   if m.group(1).strip().lower() == "moderator" or _person_label(m.group(1).strip())]
        if not roster and known_speakers:
            for m in re.finditer(r"(?m)^[ \t]*([^\n]+?)[ \t]*$", text):
                label = m.group(1).strip().rstrip(":")
                if label in known_speakers:
                    matches.append((m.start(), label))
        matches = sorted(set(matches))
        cursor, speaker = 0, carry_speaker
        for start, label in matches:
            if start > cursor:
                segments.append((text[cursor:start], speaker))
            speaker = label
            cursor = start
        segments.append((text[cursor:], speaker))
        carry_speaker = speaker
    else:
        segments = [(text, None)]
    out: List[Tuple[str, Optional[str]]] = []
    for seg, spk in segments:
        seg = seg.strip()
        while seg:
            if len(seg) <= CHUNK_CHARS:
                piece, seg = seg, ""
            else:
                cut = seg.rfind("\n", 0, CHUNK_CHARS)
                if cut < CHUNK_CHARS // 2:
                    cut = seg.rfind(". ", 0, CHUNK_CHARS)
                cut = cut + 1 if cut > CHUNK_CHARS // 3 else CHUNK_CHARS
                piece, seg = seg[:cut], seg[cut:].strip()
            if len(piece.strip()) >= 40:
                out.append((piece.strip(), spk))
    return out, carry_speaker


# ---------------------------------------------------------------- availability
def _same_doc_url(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b:
        return False
    pa, pb = urlparse(a.strip()), urlparse(b.strip())
    return pa.netloc.lower() == pb.netloc.lower() and pa.path == pb.path


def _parse_date_field(value: str) -> Tuple[Optional[str], Optional[str]]:
    ts = nse.parse_nse_timestamp(value)
    if ts:
        return ts, "second"
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            d = datetime.strptime(value.strip(), fmt).date()
            # date-only publication: conservatively available by the end of that IST day
            return datetime.combine(d, time(23, 59, 59), IST).astimezone(timezone.utc).isoformat(), "date"
        except ValueError:
            continue
    return None, None


def index_publication(record: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Latest explicit publication timestamp on a dated exchange index record.

    Some historical rows encode dissemination as midnight but carry a later
    broadcast timestamp. Taking the latest recognised field is conservative;
    arbitrary fiscal-period fields are not publication proof.
    """
    candidates = []
    for key, value in record.items():
        if not isinstance(value, str) or not re.search(r"disseminat|broadcast|submi|filing.?date|publi|^date$", key, re.I):
            continue
        stamp, precision = _parse_date_field(value)
        if stamp:
            parsed = datetime.fromisoformat(stamp)
            if precision == "second" and parsed.astimezone(IST).time() == time(0):
                parsed = parsed.astimezone(IST).replace(hour=23, minute=59, second=59).astimezone(timezone.utc)
                stamp, precision = parsed.isoformat(), "date"
            candidates.append((datetime.fromisoformat(stamp), stamp, precision, key))
    if not candidates:
        return None, None, None
    _, stamp, precision, key = max(candidates)
    return stamp, precision, key


def verify_availability(store: Store, fetcher: Fetcher, company: Company, url: str,
                        search: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], List[AvailabilityEvidence]]:
    """Find a dated exchange record whose attachment is exactly this document URL."""
    evidence: List[AvailabilityEvidence] = []
    ann = search.get("announcements")
    if ann:
        res, records = nse.fetch_announcements(fetcher, company, date.fromisoformat(ann["from"]), date.fromisoformat(ann["to"]))
        nse.store_announcements(store, company, res, records)
        if not res.ok:
            evidence.append(AvailabilityEvidence(method="exchange_announcement", source_url=res.url,
                                                 note=f"announcement query {res.state}: {res.error}"))
        for rec in records:
            if _same_doc_url(rec.get("attchmntFile"), url):
                raw = rec.get("exchdisstime") or rec.get("an_dt")
                published = nse.parse_nse_timestamp(raw)
                if published:
                    evidence.append(AvailabilityEvidence(
                        method="exchange_announcement", source_url=res.url, source_hash=res.content_hash,
                        matched_record={k: rec.get(k) for k in ("symbol", "desc", "an_dt", "exchdisstime", "attchmntFile", "attchmntText", "seq_id")},
                        note="exchange dissemination time of the record whose attachment is this document"))
                    return published, "second", evidence
        if res.ok:
            evidence.append(AvailabilityEvidence(method="exchange_announcement", source_url=res.url, source_hash=res.content_hash,
                                                 note=f"no record in {ann['from']}..{ann['to']} lists this attachment"))
    if search.get("annual_reports_api"):
        res, records = nse.fetch_annual_report_index(fetcher, company)
        if not res.ok:
            evidence.append(AvailabilityEvidence(method="exchange_annual_report_index", source_url=res.url,
                                                 note=f"annual-report index {res.state}: {res.error}"))
        for rec in records:
            values = [v for v in rec.values() if isinstance(v, str)]
            if any(_same_doc_url(v, url) for v in values):
                published, precision, key = index_publication(rec)
                if published:
                    evidence.append(AvailabilityEvidence(
                        method="exchange_annual_report_index", source_url=res.url, source_hash=res.content_hash,
                        matched_record=rec, note=f"latest explicit publication field '{key}' on the index record listing this file (conservative)"))
                    return published, precision, evidence
                evidence.append(AvailabilityEvidence(method="exchange_annual_report_index", source_url=res.url,
                                                     source_hash=res.content_hash, matched_record=rec,
                                                     note="record lists this file but carries no parseable date"))
        if res.ok and not any(e.matched_record for e in evidence if e.method == "exchange_annual_report_index"):
            evidence.append(AvailabilityEvidence(method="exchange_annual_report_index", source_url=res.url,
                                                 source_hash=res.content_hash, note="index does not list this file"))
    return None, None, evidence


# ---------------------------------------------------------------- ingestion
def ingest_document(store: Store, fetcher: Fetcher, company: Company, spec: Dict[str, Any],
                    max_pages: int = 600) -> Dict[str, Any]:
    url = spec["url"]
    doc_type = spec["doc_type"]
    document_id = "doc_" + sha256_bytes(f"{company.company_id}|{doc_type}|{url}".encode())[:16]
    res = fetcher.get(url, source_kind=f"document:{doc_type}", expect="pdf", company_id=company.company_id)
    summary: Dict[str, Any] = {"url": url, "doc_type": doc_type, "state": res.state, "error": res.error}
    if not res.ok:
        return summary
    version_id = f"ver_{res.content_hash[:16]}"
    summary["version_id"] = version_id
    existing = store.query_one("SELECT * FROM document_versions WHERE version_id=?", (version_id,))
    if existing and existing["company_id"] != company.company_id:
        return {**summary, "state": "invalid_document", "error": "identical bytes already belong to a different company"}

    published_at, precision = spec.get("_published_at"), spec.get("_precision")
    evidence = [AvailabilityEvidence(**e) for e in spec.get("_availability_evidence", [])]
    if published_at is None:
        published_at, precision, evidence = verify_availability(store, fetcher, company, url, spec.get("availability_search", {}))

    if existing and existing["availability_status"] == "verified" and existing["published_at"]:
        # A later repeat listing must not erase proof that these exact bytes
        # were already available earlier. Preserve its original dated proof.
        if published_at is None or existing["published_at"] <= published_at:
            published_at, precision = existing["published_at"], existing["published_precision"]
            evidence = [AvailabilityEvidence(**e) for e in json.loads(existing["availability_evidence"])]

    if existing and existing["parser_version"] == PARSER_VERSION and existing["doc_type"] == doc_type:
        # Same bytes already extracted; refresh availability evidence only.
        store.execute(
            "UPDATE document_versions SET published_at=?, published_precision=?, availability_status=?, availability_evidence=? WHERE version_id=?",
            (published_at, precision, "verified" if published_at else "unverified",
             json.dumps([e.model_dump() for e in evidence]), version_id),
        )
        summary.update(skipped_extraction=True, published_at=published_at)
        return summary

    pages, total_pages, parse_status = extract_pages(res.content, max_pages)
    period_info = {}
    if not spec.get("period_label") or spec.get("_discovered"):
        period_info = infer_reporting_period(pages, doc_type)
        if not spec.get("period_label"):
            spec = {**spec, **{k: v for k, v in period_info.items() if k.startswith("period_")}}
    ident = identify_document(pages, company, doc_type, spec.get("period_start"), spec.get("period_end"))
    ident.update(period_info)
    if spec.get("_discovered"):
        # Full company/base name, rather than a common first group-name token.
        head = re.sub(r"\s+", " ", " ".join(pages[:6])).lower()
        full_hits = [term for term in company_name_terms(company.legal_name)[:2]
                     if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", head)]
        ident["full_company_terms_found"] = full_hits
        ident["identity_ok"] = ident["identity_ok"] and bool(full_hits)
        if spec.get("period_label") and period_info.get("period_label"):
            same = spec["period_label"] == period_info["period_label"]
            ident["index_period_matches_header"] = same
            ident["identity_ok"] = ident["identity_ok"] and same
    known_speakers, management_speakers = transcript_speakers(pages) if doc_type == "earnings_call_transcript" else (set(), set())
    if spec.get("_discovered") and doc_type == "earnings_call_transcript":
        content = "\n".join(pages)
        turns = [m.group(1).strip() for m in SPEAKER_RE.finditer(_clean(content))
                 if m.group(1).strip().casefold() == "moderator" or _person_label(m.group(1).strip())]
        actual_people = [name for name in turns if name.casefold() != "moderator"]
        # A cover's Ref/Sub/Scrip labels are not dialogue. Require repeated
        # turns with at least one conservatively identified person.
        transcript_body = bool(re.search(r"\btranscript\b", content[:18000], re.I)) and len(turns) >= 3 and bool(actual_people)
        ident["transcript_dialogue_verified"] = transcript_body
        ident["identity_ok"] = ident["identity_ok"] and transcript_body
    if management_speakers:
        ident["management_speakers"] = sorted(management_speakers)
    host = urlparse(res.final_url or url).netloc
    store.insert("document_versions", {
        "version_id": version_id, "document_id": document_id, "company_id": company.company_id,
        "doc_type": doc_type, "period_label": spec.get("period_label"), "period_start": spec.get("period_start"),
        "period_end": spec.get("period_end"), "event_date": spec.get("event_date"),
        "source_url": url, "final_url": res.final_url, "host": host, "content_hash": res.content_hash,
        "media_type": "application/pdf", "bytes": len(res.content), "page_count": total_pages,
        "published_at": published_at, "published_precision": precision,
        "availability_status": "verified" if published_at else "unverified",
        "availability_evidence": json.dumps([e.model_dump() for e in evidence]),
        "retrieved_at": res.retrieved_at, "parse_status": parse_status, "parser_version": PARSER_VERSION,
        "identification": json.dumps(ident),
    }, mode="INSERT OR REPLACE")

    speaker_aware = doc_type == "earnings_call_transcript"
    carry: Optional[str] = None
    n = 0
    with store.connect() as conn:
        conn.execute("DELETE FROM passages WHERE version_id=?", (version_id,))
        conn.execute("DELETE FROM passages_fts WHERE version_id=?", (version_id,))
        for page_index, text in enumerate(pages, start=1):
            chunks, carry = chunk_page(text, speaker_aware, carry, known_speakers)
            for seq, (chunk, speaker) in enumerate(chunks):
                pid = f"psg_{res.content_hash[:10]}_{page_index:04d}_{seq:02d}"
                conn.execute(
                    "INSERT INTO passages VALUES (?,?,?,?,?,?,?,?)",
                    (pid, version_id, page_index, None, speaker, chunk, "extracted", seq),
                )
                conn.execute("INSERT INTO passages_fts (passage_id, version_id, text) VALUES (?,?,?)", (pid, version_id, chunk))
                n += 1
    summary.update(pages=total_pages, passages=n, parse_status=parse_status, identification=ident,
                   published_at=published_at, availability="verified" if published_at else "unverified")
    return summary


def link_announcement_attachment(store: Store, fetcher: Fetcher, company: Company, ann: Dict[str, Any],
                                 max_pages: int = 600) -> Dict[str, Any]:
    """Download an announcement's attachment as an exchange_filing whose availability is the
    record's own dissemination time."""
    spec = {
        "url": ann["attachment_url"], "doc_type": "exchange_filing", "period_label": None,
        "event_date": (ann.get("published_at") or "")[:10] or None,
        "_published_at": ann.get("published_at"), "_precision": "second" if ann.get("published_at") else None,
    }
    result = ingest_document(store, fetcher, company, spec, max_pages=max_pages)
    if result.get("version_id"):
        ev = [AvailabilityEvidence(method="exchange_announcement", source_url=ann["source_url"], source_hash=ann.get("source_hash"),
                                   matched_record=json.loads(ann["raw_json"]) if isinstance(ann.get("raw_json"), str) else None,
                                   note="dissemination time of the announcement carrying this attachment").model_dump()]
        store.execute("UPDATE document_versions SET availability_evidence=? WHERE version_id=?", (json.dumps(ev), result["version_id"]))
    store.execute(
        "UPDATE announcements SET attachment_version_id=?, attachment_state=? WHERE announcement_id=?",
        (result.get("version_id"), result["state"], ann["announcement_id"]),
    )
    # A document fetched via the manifest may be the same bytes as an attachment: link by hash.
    return result


def link_existing_versions(store: Store, company: Company) -> int:
    """Link announcements to already-stored versions whose source URL equals the attachment URL."""
    linked = 0
    for ann in store.query("SELECT announcement_id, attachment_url FROM announcements WHERE company_id=? AND attachment_url IS NOT NULL AND attachment_version_id IS NULL", (company.company_id,)):
        ver = store.query_one("SELECT version_id FROM document_versions WHERE company_id=? AND source_url=?", (company.company_id, ann["attachment_url"]))
        if ver:
            store.execute("UPDATE announcements SET attachment_version_id=?, attachment_state='fetched' WHERE announcement_id=?",
                          (ver["version_id"], ann["announcement_id"]))
            linked += 1
    return linked


def utc_now_iso() -> str:
    return utcnow()
