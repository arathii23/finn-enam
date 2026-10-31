// Thin typed client for the FINN API (same origin).

export type Replay = {
  replay_id: string; label: string; filing_from: string; filing_to: string;
  cutoff_utc: string; cutoff_display: string; prepared_symbols: string[];
};
export type Health = {
  status: string; model_configured: boolean; model_primary: string; replay: Replay | null;
  corpus: Record<string, number>; frontend_built: boolean;
};
export type Company = {
  company_id: string; symbol: string; legal_name: string; exchange: string; isin: string; series: string;
  listing_date: string | null; identity_source_url: string; identity_source_hash: string; resolved_at: string;
};
export type AvailabilityEvidence = { method: string; source_url?: string | null; note?: string | null; matched_record?: Record<string, unknown> | null };
export type DocVersion = {
  version_id: string; doc_type: string; period_label: string | null; event_date: string | null;
  source_url: string; host: string; content_hash: string; bytes: number; page_count: number | null;
  published_at: string | null; published_precision: "second" | "date" | null; availability_status: string;
  availability_evidence: AvailabilityEvidence[]; retrieved_at: string; parse_status: string;
  identification: Record<string, unknown> | null; exclusion_reasons: string[];
};
export type Announcement = {
  announcement_id: string; category: string | null; subject: string | null; published_at: string | null;
  published_at_raw: string | null; attachment_url: string | null; attachment_version_id: string | null;
  attachment_state: string | null; retrieved_at: string; source_url: string;
};
export type Eod = {
  trading_date: string; close: number | null; prev_close: number | null; volume: number | null;
  series: string; source_url: string; source_hash: string; validation_status: string;
};
export type Overview = {
  company: Company; mode: string; replay: Replay | null; announcements: Announcement[]; eod: Eod[];
  documents: { eligible: DocVersion[]; excluded: DocVersion[] };
  coverage: { source_kind: string; state: string; n: number; last: string }[];
};
export type Claim = { text: string; evidence_ids: string[]; speaker?: string | null };
export type Section = { status: string; claims: Claim[]; candidate_evidence_ids: string[]; note?: string | null };
export type EvidenceIndexEntry = { version_id: string; doc_type: string; period_label: string | null; page_index: number; speaker: string | null; published_at: string | null; excerpt: string };
export type ResearchOutput = {
  research_id: string; company: Company; mode: string; cutoff: string | null; question: string | null;
  event: Announcement | null; eligible_version_ids: string[];
  excluded_documents: { doc_type: string; period_label: string | null; reasons: string[] }[];
  business_context: Section; management_commentary: Section; event_filing: Section | null;
  evidence_gaps: { kind: string; text: string; evidence_ids: string[] }[];
  follow_up: { status: string; text: string | null; evidence_ids: string[] };
  generation: { status: string; reason: string | null; model: string | null; usage: Record<string, unknown> };
  generated_at: string; evidence_index: Record<string, EvidenceIndexEntry>; removed_claims: unknown[];
};
export type Job = {
  job_id: string; state: string; stage: string | null; error: string | null; created_at: string; updated_at: string;
  stages: { stage: string; started_at: string; finished_at: string | null }[]; all_stages: string[];
  request: { symbol: string; question: string | null; event_id: string | null; mode: string };
  result: ResearchOutput | null;
};
export type Evidence = {
  passage: { passage_id: string; version_id: string; page_index: number; printed_page: string | null; printed_page_reason: string | null; speaker: string | null; text: string };
  document: DocVersion; company: Company;
  same_page_passages: { passage_id: string; text: string }[];
};

export type QueueEvent = {
  announcement_id: string; category: string | null; ref_category: string; reason: string; tier: number;
  published_at: string | null; subject: string | null; attachment_version_id: string | null; attachment_url: string | null;
};
export type EodAnomaly = {
  trading_date: string; close: number | null; prev_close: number | null; volume: number | null;
  price_move_pct: number | null; volume_ratio: number | null; flags: string[]; flagged: boolean;
  basis: string; notes: string[];
};
export type QueueCompany = {
  symbol: string; legal_name?: string; status: "ok" | "no_data" | "unresolved";
  coverage: { identity: boolean; announcements: number; eod: number; documents: number };
  leading_events?: QueueEvent[]; notable_events?: QueueEvent[]; routine_count?: number;
  eod_anomaly?: EodAnomaly | null; can_research?: boolean;
};
export type PortfolioQueue = {
  mode: string; replay: Replay | null;
  thresholds: { price_move_pct: number; volume_multiple: number; baseline_sessions: number; min_baseline_sessions: number };
  summary: { companies: number; checked: number; with_events: number; price_volume_flagged: number };
  companies: QueueCompany[];
};

export class ApiError extends Error {
  constructor(public status: number, public state: string, message: string) { super(message); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new ApiError(0, "network", "The FINN server could not be reached.");
  }
  const body = await resp.json().catch(() => null);
  if (!resp.ok) {
    const d = body?.detail;
    throw new ApiError(resp.status, d?.state ?? "error", d?.message ?? (typeof d === "string" ? d : `HTTP ${resp.status}`));
  }
  return body as T;
}

export const api = {
  health: () => call<Health>("/api/health"),
  overview: (symbol: string) => call<Overview>(`/api/companies/${encodeURIComponent(symbol)}/overview?mode=replay`),
  research: (body: { symbol: string; question?: string; event_id?: string; mode: "replay"; retry?: boolean }) =>
    call<{ job_id: string; reused: boolean }>("/api/research", { method: "POST", body: JSON.stringify(body) }),
  job: (id: string) => call<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  evidence: (id: string) => call<Evidence>(`/api/evidence/${encodeURIComponent(id)}`),
  portfolio: (opts?: { priceMovePct?: number; volumeMultiple?: number }) => {
    const q = new URLSearchParams({ mode: "replay" });
    if (opts?.priceMovePct != null) q.set("price_move_pct", String(opts.priceMovePct));
    if (opts?.volumeMultiple != null) q.set("volume_multiple", String(opts.volumeMultiple));
    return call<PortfolioQueue>(`/api/portfolio?${q.toString()}`);
  },
  fileUrl: (versionId: string, page?: number) => `/api/documents/${encodeURIComponent(versionId)}/file${page ? `#page=${page}` : ""}`,
};
