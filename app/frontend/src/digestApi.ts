import { IS_STATIC } from "./api";
import type { SourceChecks } from "./FreshnessLine";

export type DigestItem = {
  id: string; version: string; symbol: string; published_at: string; category: string;
  base_tier: number; tier: number; tier_reason: string; subject: string; updated?: boolean;
  source: { url: string } | null;
};
export type Digest = {
  schema: 1; generated_at: string;
  checks: SourceChecks & { holdings_total: number; holdings_checked: number };
  window: { from: string; to: string; days: number };
  items: DigestItem[];
};

const URL = IS_STATIC ? import.meta.env.VITE_DIGEST_URL as string | undefined : "/api/digest";
const CACHE = "finn.digest.v1";
const MAX_AGE = 14 * 86400000;
const LIMIT = 2_000_000;

export function filingLink(value?: string) {
  if (!value) return null;
  try {
    const url = new window.URL(value);
    return url.protocol === "https:" && !url.username && !url.password && !url.port &&
      /^(?:(?:nsearchives|www|archives)\.)?nseindia\.(?:in|com)$/.test(url.hostname) ? value : null;
  } catch { return null; }
}

function parse(raw: string): Digest {
  if (raw.length > LIMIT) throw Error("Digest exceeds its size limit");
  const d: Digest = JSON.parse(raw);
  const generated = Date.parse(d?.generated_at);
  if (d?.schema !== 1 || !Number.isFinite(generated) || generated > Date.now() + 60000 ||
      Date.now() - generated > MAX_AGE || !Array.isArray(d.checks?.holdings) || !d.window ||
      !Array.isArray(d.items) || d.items.length > 2000) throw Error("Invalid or expired digest");
  const rows = d.checks.holdings;
  const symbols = new Set(rows.map((r) => r.symbol));
  const checked = rows.filter((r) => r.state === "fetched");
  const finished = Date.parse(d.checks.finished_at ?? "");
  if (rows.length < 1 || rows.length > 15 || rows.length !== symbols.size || rows.length !== d.checks.holdings_total ||
      checked.length !== d.checks.holdings_checked || (checked.length > 0 && (!Number.isFinite(finished) || finished > generated)) ||
      rows.some((r) => typeof r.symbol !== "string" || !["fetched", "timeout", "error", "not_checked"].includes(r.state)) ||
      checked.some((r) => !Number.isFinite(Date.parse(r.checked_at ?? "")) || Date.parse(r.checked_at!) > generated)) throw Error("Invalid coverage");
  const ids = new Set();
  for (const item of d.items) {
    if (!symbols.has(item.symbol) || !/^ann_[a-zA-Z0-9_-]+$/.test(item.id) || ids.has(item.id) ||
        !/^[a-f0-9]{16}$/.test(item.version) || !Number.isFinite(Date.parse(item.published_at)) ||
        Date.parse(item.published_at) > generated || ![1, 2, 3].includes(item.tier) || item.base_tier !== item.tier ||
        typeof item.subject !== "string" || typeof item.tier_reason !== "string" ||
        (item.source && !filingLink(item.source.url))) throw Error("Invalid filing");
    ids.add(item.id);
  }
  return d;
}

export async function loadDigest(signal: AbortSignal): Promise<{ digest: Digest | null; cached: boolean }> {
  if (!URL) return { digest: null, cached: false };
  const request = new AbortController();
  const cancel = () => request.abort();
  signal.addEventListener("abort", cancel, { once: true });
  const timeout = window.setTimeout(cancel, IS_STATIC ? 4500 : 75000);
  try {
    const response = await fetch(URL, { cache: "no-cache", signal: request.signal });
    if (!response.ok) throw Error("Digest unavailable");
    const raw = await response.text();
    const digest = parse(raw);
    if (IS_STATIC && !digest.checks.holdings_checked) throw Error("Unverified static digest");
    try { localStorage.setItem(CACHE, raw); } catch { /* displaying a digest needs no storage */ }
    return { digest, cached: false };
  } catch {
    if (signal.aborted) return { digest: null, cached: false };
    try {
      const cached = localStorage.getItem(CACHE);
      if (cached) return { digest: parse(cached), cached: true };
    } catch { /* no usable cached digest */ }
    return { digest: null, cached: false };
  } finally {
    window.clearTimeout(timeout);
    signal.removeEventListener("abort", cancel);
  }
}
