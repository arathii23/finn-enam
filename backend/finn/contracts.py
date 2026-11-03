"""Pydantic contracts shared by ingestion, research and the HTTP API.

Timestamps are ISO-8601 strings stored in UTC. Unknown values are null with a reason
field rather than guessed values.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

RetrievalState = Literal["not_attempted", "fetched", "blocked", "not_found", "invalid_document", "timeout", "error"]
ExtractionState = Literal["extracted", "partial", "failed", "ambiguous"]
AvailabilityStatus = Literal["verified", "unverified"]
Mode = Literal["replay", "live"]
JobState = Literal["queued", "running", "completed", "partial", "failed", "interrupted"]
DocType = Literal["annual_report", "earnings_call_transcript", "exchange_filing"]


class Company(BaseModel):
    company_id: str
    symbol: str
    legal_name: str
    exchange: str = "NSE"
    isin: str
    series: str
    listing_date: Optional[str] = None
    identity_source_url: str
    identity_source_hash: str
    resolved_at: str


class FetchAttempt(BaseModel):
    attempt_id: str
    source_kind: str
    url: str
    final_url: Optional[str] = None
    state: RetrievalState
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    bytes: Optional[int] = None
    content_hash: Optional[str] = None
    error: Optional[str] = None
    company_id: Optional[str] = None
    started_at: str
    finished_at: Optional[str] = None


class Announcement(BaseModel):
    announcement_id: str
    company_id: str
    source_key: str
    category: Optional[str] = None
    subject: Optional[str] = None
    published_at: Optional[str] = None
    published_at_raw: Optional[str] = None
    attachment_url: Optional[str] = None
    attachment_version_id: Optional[str] = None
    attachment_state: Optional[str] = None
    retrieved_at: str
    source_url: str
    source_hash: Optional[str] = None


class AvailabilityEvidence(BaseModel):
    method: str
    source_url: Optional[str] = None
    source_hash: Optional[str] = None
    matched_record: Optional[Dict[str, Any]] = None
    note: Optional[str] = None


class DocumentVersion(BaseModel):
    version_id: str
    document_id: str
    company_id: str
    doc_type: DocType
    period_label: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    event_date: Optional[str] = None
    source_url: str
    final_url: Optional[str] = None
    host: str
    content_hash: str
    media_type: str
    bytes: int
    page_count: Optional[int] = None
    published_at: Optional[str] = None
    published_precision: Optional[Literal["second", "date"]] = None
    availability_status: AvailabilityStatus
    availability_evidence: List[AvailabilityEvidence] = Field(default_factory=list)
    retrieved_at: str
    parse_status: ExtractionState
    parser_version: str
    identification: Dict[str, Any] = Field(default_factory=dict)


class Passage(BaseModel):
    passage_id: str
    version_id: str
    page_index: int  # one-based PDF page index
    printed_page: Optional[str] = None
    printed_page_reason: Optional[str] = "not identified by parser"
    speaker: Optional[str] = None
    text: str
    extraction_status: ExtractionState


class MarketObservation(BaseModel):
    symbol: str
    series: str
    isin: Optional[str] = None
    trading_date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    prev_close: Optional[float] = None
    volume: Optional[int] = None
    volume_unit: str = "shares"
    basis: str = "raw (unadjusted)"
    source_url: str
    source_hash: str
    schema_version: str
    retrieved_at: str
    validation_status: str


class ResearchRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    question: Optional[str] = Field(default=None, max_length=300)
    event_id: Optional[str] = None
    mode: Mode = "replay"
    retry: bool = False


class Claim(BaseModel):
    text: str
    evidence_ids: List[str]
    speaker: Optional[str] = None


class SectionResult(BaseModel):
    status: Literal["generated", "model_unavailable", "insufficient_evidence", "failed"]
    claims: List[Claim] = Field(default_factory=list)
    candidate_evidence_ids: List[str] = Field(default_factory=list)
    note: Optional[str] = None


class Gap(BaseModel):
    kind: Literal["coverage", "model", "validation", "generated"]
    text: str
    evidence_ids: List[str] = Field(default_factory=list)


class BriefItem(BaseModel):
    """One verbatim extract selected from a primary-source passage. No model wrote it."""
    kind: Literal["business_context", "management_commentary", "event_filing"]
    quote: str
    speaker: Optional[str] = None
    doc_type: str
    period_label: Optional[str] = None
    evidence_id: str
    page_index: int


class SourceBrief(BaseModel):
    """A query-aware extractive brief built without any model call.

    Highlights are exact sentences lifted from eligible primary sources and ranked by
    keyword relevance. Numbers are quoted, never computed; nothing is written from memory.
    """
    status: Literal["extractive", "empty"]
    headline: Optional[str] = None
    method: str = ("Verbatim extracts selected from eligible primary sources by keyword relevance. "
                   "No model generated this text; figures are quoted, not computed or compared.")
    query_terms: List[str] = Field(default_factory=list)
    highlights: List[BriefItem] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)


class FollowUp(BaseModel):
    status: Literal["generated", "model_unavailable", "failed"]
    text: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)


class GenerationInfo(BaseModel):
    status: Literal["generated", "model_unavailable", "failed", "budget_exhausted", "skipped_no_evidence"]
    reason: Optional[str] = None
    model: Optional[str] = None
    prompt_version: str
    schema_version: str
    usage: Dict[str, Any] = Field(default_factory=dict)


class ResearchOutput(BaseModel):
    research_id: str
    company: Company
    mode: Mode
    cutoff: Optional[str] = None
    question: Optional[str] = None
    event: Optional[Announcement] = None
    eligible_version_ids: List[str]
    excluded_documents: List[Dict[str, Any]]
    business_context: SectionResult
    management_commentary: SectionResult
    event_filing: Optional[SectionResult] = None
    evidence_gaps: List[Gap]
    follow_up: FollowUp
    generation: GenerationInfo
    corpus_fingerprint: str
    generated_at: str
    removed_claims: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_index: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    discovery: Dict[str, Any] = Field(default_factory=dict)
    source_brief: Optional[SourceBrief] = None
