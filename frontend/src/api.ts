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
export type BriefItem = { kind: string; quote: string; speaker: string | null; doc_type: string; period_label: string | null; evidence_id: string; page_index: number };
export type SourceBrief = { status: string; headline: string | null; method: string; query_terms: string[]; highlights: BriefItem[]; suggested_questions: string[] };
export type ResearchOutput = {
  research_id: string; company: Company; mode: string; cutoff: string | null; question: string | null;
  event: Announcement | null; eligible_version_ids: string[];
  excluded_documents: { doc_type: string; period_label: string | null; reasons: string[] }[];
  business_context: Section; management_commentary: Section; event_filing: Section | null;
  evidence_gaps: { kind: string; text: string; evidence_ids: string[] }[];
  follow_up: { status: string; text: string | null; evidence_ids: string[] };
  generation: { status: string; reason: string | null; model: string | null; usage: Record<string, unknown> };
  generated_at: string; evidence_index: Record<string, EvidenceIndexEntry>; removed_claims: unknown[];
  source_brief?: SourceBrief | null;
};
export type Job = {
  job_id: string; state: string; stage: string | null; error: string | null; created_at: string; updated_at: string;
  stages: { stage: string; started_at: string; finished_at: string | null }[]; all_stages: string[];
  request: { symbol: string; question: string | null; event_id: string | null; mode: string };
  result: ResearchOutput | null;
};
export type SavedResearchItem = {
  job_id: string; symbol: string; legal_name: string; question: string | null; event_id: string | null;
  mode: string; generated_at: string; state: string; document_count: number;
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
  leading_events?: QueueEvent[]; notable_events?: QueueEvent[]; routine_count?: number; routine_events?: QueueEvent[];
  eod_anomaly?: EodAnomaly | null; can_research?: boolean;
};
export type PortfolioQueue = {
  mode: string; replay: Replay | null;
  window: { preset: string; from: string | null; to: string; filing_from: string | null; filing_to: string; label: string; stored_only: boolean };
  thresholds: { price_move_pct: number; volume_multiple: number; baseline_sessions: number; min_baseline_sessions: number };
  summary: { companies: number; checked: number; with_events: number; price_volume_flagged: number };
  companies: QueueCompany[];
};

export type NarrativeStatement = {
  value_text: string; low: number; high: number; basis: string;
  evidence_id: string; speaker: string | null; source_period: string | null; doc_type: string;
  entity?: string;
  reporting_currency?: string;
};
export type NarrativeItem = {
  metric: string; metric_key: string; fiscal_year: string; basis: string;
  entity?: string;
  reporting_currency?: string;
  guidance: NarrativeStatement; outcome: NarrativeStatement | null;
  comparable: boolean; gate_reasons: string[];
  verdict: { kind: string; delta_pp: number | null; summary: string };
  caveats: { text: string; evidence_ids: string[] }[];
};
export type Narrative = {
  symbol: string; legal_name: string; cutoff_display: string | null; company: Company;
  mode: string; items: NarrativeItem[]; method: string; empty_reason: string | null;
  evidence_index: Record<string, EvidenceIndexEntry>;
  sources: { version_id: string; doc_type: string; period_label: string | null }[];
};

export type QMetric = {
  key: string; label: string; unit: string | null; evidence_id: string | null;
  current: { value_text: string; value: number };
  previous_quarter: { value_text: string; value: number } | null;
  year_ago_quarter: { value_text: string; value: number } | null;
  qoq_pct: number | null; yoy_pct: number | null;
  source?: { version_id: string; page_index: number };
};
export type Quarterly = {
  symbol: string; legal_name: string; mode: string; available: boolean; served?: string; reason?: string;
  can_extract?: boolean; extraction_required?: boolean; warnings?: string[]; validation_version?: string;
  basis?: string | null;
  columns?: { current: string | null; previous_quarter: string | null; year_ago_quarter: string | null; current_end?: string | null };
  metrics?: QMetric[]; omitted?: { metric: string; reason: string }[];
  source?: { version_id: string; period_label: string | null; published_at: string | null; page_index: number };
  generation?: { model: string | null; usage: Record<string, unknown> };
};

export type ManagementChanges = {
  symbol: string; mode: string; served: "deterministic"; method: string; empty_reason: string | null;
  items: {
    name: string; role: string; effective_date_text: string; change: string;
    profile_quote: string; appointment_evidence_id: string; profile_evidence_id: string;
    appointment_page_index: number; profile_page_index: number;
    announcement_id: string; version_id: string; published_at: string; in_review_window: boolean;
  }[];
};

export type LivePriceCompany = {
  symbol: string; state: string; error?: string; currency?: string; exchange?: string; sessions?: number;
  latest?: { trading_date: string; close: number; prev_close: number | null; volume: number | null };
  anomaly?: { flagged: boolean; price_move_pct: number | null; volume_ratio: number | null; flags: string[]; notes: string[] } | null;
  source_url?: string; retrieved_at?: string;
};
export type LivePrices = {
  source: string; thresholds: { price_move_pct: number; volume_multiple: number };
  summary: { companies: number; flagged: number; ok: number };
  companies: LivePriceCompany[]; retrieved_at: string; disclaimer: string;
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

// Static snapshot mode: the app is a read-only CDN bundle with no backend. Each API call maps
// to a pre-exported JSON file; writes and on-demand research are disabled with a clear message.
export const IS_STATIC = import.meta.env.VITE_STATIC === "1";
const SNAP = `${import.meta.env.BASE_URL}snapshot/`;

let docsCache: Record<string, { source_url: string; final_url: string | null; host: string }> | null = null;
async function ensureDocs(): Promise<void> {
  if (docsCache) return;
  try { docsCache = await (await fetch(`${SNAP}documents.json`)).json(); } catch { docsCache = {}; }
}

async function snap<T>(file: string, needDocs = false): Promise<T> {
  if (needDocs) await ensureDocs();
  let resp: Response;
  try { resp = await fetch(`${SNAP}${file}`); } catch { throw new ApiError(0, "network", "The snapshot file could not be loaded."); }
  if (!resp.ok) {
    throw new ApiError(resp.status, resp.status === 404 ? "not_in_snapshot" : "error",
      resp.status === 404 ? "This item is not part of the static snapshot. Open the live app for on-demand data." : `Snapshot HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

const STATIC_RESEARCH = () => Promise.reject(new ApiError(0, "static_mode",
  "On-demand research runs on the live FINN backend. In this static demo you can browse the Push digest, the saved research briefs and all primary-source evidence."));

const liveApi = {
  health: () => call<Health>("/api/health"),
  overview: (symbol: string) => call<Overview>(`/api/companies/${encodeURIComponent(symbol)}/overview?mode=replay`),
  narrative: (symbol: string) => call<Narrative>(`/api/companies/${encodeURIComponent(symbol)}/narrative?mode=replay`),
  quarterly: (symbol: string) => call<Quarterly>(`/api/companies/${encodeURIComponent(symbol)}/quarterly?mode=replay`),
  extractQuarterly: (symbol: string) => call<Quarterly>(`/api/companies/${encodeURIComponent(symbol)}/quarterly/extract?mode=replay`, { method: "POST" }),
  management: (symbol: string) => call<ManagementChanges>(`/api/companies/${encodeURIComponent(symbol)}/management?mode=replay`),
  research: (body: { symbol: string; question?: string; event_id?: string; mode: "replay"; retry?: boolean }) =>
    call<{ job_id: string; reused: boolean }>("/api/research", { method: "POST", body: JSON.stringify(body) }),
  job: (id: string) => call<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  savedResearch: (symbol?: string) => call<{ items: SavedResearchItem[] }>(`/api/research/saved${symbol ? `?symbol=${encodeURIComponent(symbol)}` : ""}`),
  evidence: (id: string) => call<Evidence>(`/api/evidence/${encodeURIComponent(id)}`),
  portfolio: (opts?: { priceMovePct?: number; volumeMultiple?: number; window?: string; filingFrom?: string; filingTo?: string }) => {
    const q = new URLSearchParams({ mode: "replay" });
    if (opts?.priceMovePct != null) q.set("price_move_pct", String(opts.priceMovePct));
    if (opts?.volumeMultiple != null) q.set("volume_multiple", String(opts.volumeMultiple));
    if (opts?.window) q.set("window", opts.window);
    if (opts?.filingFrom) q.set("filing_from", opts.filingFrom);
    if (opts?.filingTo) q.set("filing_to", opts.filingTo);
    return call<PortfolioQueue>(`/api/portfolio?${q.toString()}`);
  },
  livePrices: (opts?: { priceMovePct?: number; volumeMultiple?: number }) => {
    const q = new URLSearchParams();
    if (opts?.priceMovePct != null) q.set("price_move_pct", String(opts.priceMovePct));
    if (opts?.volumeMultiple != null) q.set("volume_multiple", String(opts.volumeMultiple));
    const qs = q.toString();
    return call<LivePrices>(`/api/live-prices${qs ? `?${qs}` : ""}`);
  },
  fileUrl: (versionId: string, page?: number) => `/api/documents/${encodeURIComponent(versionId)}/file${page ? `#page=${page}` : ""}`,
};

const sym = (s: string) => encodeURIComponent(s.trim().toUpperCase());
const staticApi: typeof liveApi = {
  health: () => snap<Health>("health.json"),
  overview: (s: string) => snap<Overview>(`overview_${sym(s)}.json`, true),
  narrative: (s: string) => snap<Narrative>(`narrative_${sym(s)}.json`, true),
  quarterly: (s: string) => snap<Quarterly>(`quarterly_${sym(s)}.json`),
  extractQuarterly: STATIC_RESEARCH as typeof liveApi.extractQuarterly,
  management: (s: string) => snap<ManagementChanges>(`management_${sym(s)}.json`, true),
  research: STATIC_RESEARCH as typeof liveApi.research,
  job: (id: string) => snap<Job>(`job_${encodeURIComponent(id)}.json`, true),
  savedResearch: (symbol?: string) => snap<{ items: SavedResearchItem[] }>(symbol ? `saved_${sym(symbol)}.json` : "saved.json")
    .catch((e) => { if (e instanceof ApiError && e.status === 404) return { items: [] }; throw e; }),
  evidence: (id: string) => snap<Evidence>(`evidence_${encodeURIComponent(id)}.json`, true),
  portfolio: (opts?: { window?: string }) => {
    const w = opts?.window && ["24h", "7d", "all"].includes(opts.window) ? opts.window : "24h";
    return snap<PortfolioQueue>(`portfolio_${w}.json`, true);
  },
  livePrices: ((() => {
    const url = import.meta.env.VITE_LIVE_PRICES_URL;
    if (!url) return Promise.reject(new ApiError(0, "static_mode", "Live prices are not configured for this build."));
    // Cache-bust lightly so a viewer sees fresh data within the scheduler's cadence.
    return fetch(`${url}${url.includes("?") ? "&" : "?"}t=${Math.floor(Date.now() / 60000)}`)
      .then((r) => { if (!r.ok) throw new ApiError(r.status, "live_feed", r.status === 404 ? "The live feed is initialising — the scheduled refresh runs every few minutes." : `Live feed HTTP ${r.status}`); return r.json() as Promise<LivePrices>; })
      .catch((e) => { if (e instanceof ApiError) throw e; throw new ApiError(0, "network", "The live price feed could not be reached."); });
  })) as typeof liveApi.livePrices,
  fileUrl: (versionId: string, page?: number) => {
    const d = docsCache?.[versionId];
    const url = d?.final_url || d?.source_url;
    return url ? `${url}${page && /\.pdf($|[?#])/i.test(url) ? `#page=${page}` : ""}` : "#";
  },
};

export const api = IS_STATIC ? staticApi : liveApi;
