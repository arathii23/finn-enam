"""Conservative appointment profiles copied from primary exchange filings.

The announcement supplies a candidate identity only. Name, role, date and profile
must be read from the linked filing; unsupported layouts are omitted. No model,
outside biography, inferred date or ticker-specific rule is used.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_HONORIFIC = r"(?:Mrs|Mr|Ms|Dr|Shri|Smt)\b\s*\.?\s*"
_NAME = _HONORIFIC + r"[A-Z][\w’'.-]*(?:\s+[A-Z][\w’'.-]*){1,5}"
_SUBJECT = re.compile(r"\b(?:re-)?appointment\s+of\s+(?P<name>" + _NAME + r")\s+as\b", re.I)
_PERSON = re.compile(_NAME)
_MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
_DATE = r"(?:" + _MONTH + r"\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*\d{4}|\d{1,2}\s*(?:st|nd|rd|th)?\s+" + _MONTH + r"\s*,?\s*\d{4})"
_EFFECTIVE = r"(?:w\s*\.\s*e\s*\.\s*f\s*\.?|with effect from|effective(?: from)?)"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _identity(text: str) -> str:
    return re.sub(r"[^a-z]", "", re.sub(r"^" + _HONORIFIC, "", text, flags=re.I).lower())


def _profile_excerpt(text: str) -> str:
    """At most three complete sentences, kept as one contiguous source quote."""
    text = re.split(r"\s+(?:\d+\.\s*)?Disclosure of relationship\b", text, flags=re.I)[0].strip()
    ends = list(re.finditer(r"[.!?](?=\s+(?:[A-Z]|$)|$)", text))
    # Mr./Dr. are not sentence boundaries. Don't cut a sentence to fit the card.
    ends = [m for m in ends if not re.search(r"\b(?:Mr|Mrs|Ms|Dr)$", text[:m.start()])]
    if not ends:
        return ""
    stop = ends[0].end()
    for m in ends[1:3]:
        if m.end() > 650:
            break
        stop = m.end()
    return text[:stop] if stop <= 900 else ""


def extract_appointment(subject: str, passages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return a fully source-bound profile, or None for an ambiguous/missing field.

    Caller passes passages of ONE eligible, announcement-linked filing. Requiring
    exactly one named appointment and matching profile avoids cross-person bios.
    """
    seed = list(_SUBJECT.finditer(_norm(subject)))
    if len(seed) != 1:
        return None
    identity = _identity(seed[0]["name"])
    fields = None
    for p in passages:
        text = _norm(p["text"])
        for person in _PERSON.finditer(text):
            if _identity(person[0]) != identity:
                continue
            tail = text[person.end():]
            appointed = re.match(r"\s+has been (?P<renewal>re-)?appointed as\s+[‘'\"]?(?P<role>[^.!?]+?)[’'\"]?\s+" + _EFFECTIVE + r"\s*(?P<date>" + _DATE + r")", tail, re.I)
            inclusion = re.match(r"\s*[–—-]\s*(?P<role>[^.!?]+?)\s+as part of the Senior Management\b", tail, re.I)
            if appointed:
                # The date must immediately follow this appointment's own marker.
                date_match = appointed
                change = "Reappointment" if appointed["renewal"] else "Appointment"
            elif inclusion and re.search(r"approved the inclusion of\s*$", text[:person.start()], re.I):
                # Inclusion in senior management is not a new hire or a new role.
                before = re.search(r"today i\.e\.\s*(?P<date>" + _DATE + r").{0,100}approved the inclusion of\s*$", text[:person.start()], re.I)
                date_match = before if re.search(r"with immediate effect", tail[:inclusion.end() + 80], re.I) else None
                change = "Inclusion in senior management"
            else:
                continue
            role_match = appointed or inclusion
            role = role_match["role"].rstrip("’'\"").strip()
            if not date_match or len(role) > 180 or not re.search(r"head|officer|director|president|manager|secretary|chief|\b(?:CEO|CFO|COO|MD)\b", role, re.I):
                continue
            fields = {"name": person[0], "role": role, "effective_date_text": date_match["date"],
                      "change": change, "appointment_evidence_id": p["passage_id"],
                      "appointment_page_index": p["page_index"]}
            break
        if fields:
            break
    if not fields:
        return None

    for p in passages:
        text = _norm(p["text"])
        header = re.search(r"\bBrief Profile(?:\s+of\s+" + re.escape(fields["name"]) + r")?\s*:?\s*", text)
        if not header:
            continue
        profile = _profile_excerpt(text[header.end():])
        people = list(_PERSON.finditer(profile))
        # Some filings omit the dot in "Mr". That is still the same named person.
        if not profile or not people or _identity(people[0][0]) != identity:
            continue
        if any(_identity(person[0]) != identity for person in people):
            continue
        return {**fields, "profile_quote": profile, "profile_evidence_id": p["passage_id"],
                "profile_page_index": p["page_index"]}
    return None
