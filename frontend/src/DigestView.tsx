import { useEffect, useState, type ReactNode } from "react";
import { api, IS_STATIC } from "./api";
import { loadDigest, filingLink, type Digest, type DigestItem } from "./digestApi";
import { FreshnessLine } from "./FreshnessLine";
import { istDateTime } from "./format";
import { markAll, markOne, readVisit, wasCleared, writeVisit, type Visit } from "./lastVisit";
import { liveAppUrl, researchPath, savedBriefsUrl } from "./links";
import { LivePricesCard } from "./QueueView";
import { StateBox } from "./ui";

const categories: Record<string, string> = { credit_rating: "Credit rating", management_change: "Management", litigation: "Regulatory / legal", results: "Results", M_and_A: "M&A", unclassified: "Filing" };
type Window = "since" | "24h" | "7d";

function FilingCard({ item, visit, onSeen, onOpenCompany }: { item: DigestItem; visit: Visit;
  onSeen: (item: DigestItem) => void; onOpenCompany: (symbol: string) => void }) {
  const seen = visit.seen[item.id] === item.version || wasCleared(visit, item);
  const revised = item.updated || (visit.cleared[item.id] && visit.cleared[item.id] !== item.version);
  const url = filingLink(item.source?.url);
  return <li className={`digest-card${seen ? " digest-seen" : ""}`}>
    <p className="fine"><strong>{item.symbol}</strong> · {categories[item.category] ?? item.category.replace(/_/g, " ")} · {istDateTime(item.published_at)}</p>
    {revised && <p className="fine"><strong>Updated filing details</strong></p>}
    <p className="digest-subject">{item.subject}</p>
    <p className="fine">{item.tier_reason} · Exchange subject only</p>
    <div className="digest-actions">
      {url ? <a className="btn btn-small" href={url} target="_blank" rel="noopener noreferrer">Open filing ↗</a> : <span className="fine">No verified attachment link</span>}
      <button className="btn btn-small btn-ghost" onClick={() => onOpenCompany(item.symbol)}>Company</button>
      {!seen && <button className="btn btn-small btn-ghost" onClick={() => onSeen(item)}>Seen</button>}
      {!IS_STATIC && <a className="btn btn-small btn-ghost" href={`#${researchPath({symbol: item.symbol, mode: "live", eventId: item.id, question: "What does this exchange filing say?"})}`}>Ask about this</a>}
    </div>
  </li>;
}

export function DigestView({ fallback, onOpenCompany }: { fallback: ReactNode; onOpenCompany: (symbol: string) => void }) {
  const [result, setResult] = useState<{ digest: Digest | null; cached: boolean }>();
  const [visit, setVisit] = useState(readVisit);
  const [period, setPeriod] = useState<Window>("since");
  const [refresh, setRefresh] = useState(0);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    loadDigest(controller.signal).then((response) => { if (!controller.signal.aborted) setResult(response); });
    return () => controller.abort();
  }, [refresh]);

  const check = async () => {
    setChecking(true); setCheckError("");
    try { await api.refreshPortfolio(); setRefresh((n) => n + 1); }
    catch { setCheckError("The exchange check did not complete. Earlier records remain visible."); }
    finally { setChecking(false); }
  };

  if (!result) return <StateBox kind="loading" title="Opening your portfolio brief…">
    {IS_STATIC ? "Reading the saved filing digest." : <>The free service can take some time to wake. <a href={savedBriefsUrl}>Open saved briefs</a></>}
  </StateBox>;
  if (!result.digest) return <div className="stack">
    <StateBox kind="info" title="Current digest unavailable. Showing the historical replay." />
    {fallback}
  </div>;

  const { digest, cached } = result;
  const generated = Date.parse(digest.generated_at);
  const span = period === "24h" ? 86400000 : (period === "since" && visit.visit.watermark ? 14 : 7) * 86400000;
  const candidates = digest.items.filter((item) => Date.parse(item.published_at) >= generated - span);
  const visible = candidates.filter((item) => period !== "since" || !wasCleared(visit.visit, item));
  const unacknowledged = candidates.filter((item) => !wasCleared(visit.visit, item));
  const quiet = digest.checks.holdings.filter((row) => row.state === "fetched" && row.announcements === 0);
  const updateVisit = (value: Visit) => setVisit({ visit: value, unavailable: !writeVisit(value) });
  const activeCount = visible.filter((item) => item.tier === 1 || item.tier === 2).length;
  const cards = (tier: number) => visible.filter((item) => item.tier === tier)
    .map((item) => <FilingCard key={item.id} item={item} visit={visit.visit}
      onSeen={(row) => updateVisit(markOne(visit.visit, row))} onOpenCompany={onOpenCompany} />);

  return <div className="stack portfolio-digest">
    <section className="card digest-intro">
      <h1>Since your last visit</h1>
      <p className="fine">{!visit.visit.watermark ? "First visit · last 7 days" : `Last acknowledged ${istDateTime(visit.visit.watermark)}`} · {digest.checks.holdings_total} holdings</p>
      <p className="fine">Manual digest · as of {istDateTime(digest.generated_at)}{cached && " · latest unavailable, saved copy shown"}</p>
      <FreshnessLine checks={digest.checks} action={IS_STATIC
        ? <a className="btn btn-small" href={liveAppUrl({ mode: "live" }).replace(/#.*$/, "#/")}>Open live app ↗ (may take about a minute to wake)</a>
        : <button className="btn btn-small" onClick={check} disabled={checking}>{checking ? "Checking exchange…" : "Check latest filings"}</button>} />
      {checkError && <p role="status" className="fine">{checkError}</p>}
      {visit.unavailable && <p role="status" className="fine">Seen markers cannot be saved in this browser.</p>}
      <div className="digest-actions" aria-label="Digest period">
        {([["since", "Since last visit"], ["24h", "24 h"], ["7d", "7 days"]] as const).map(([key, label]) =>
          <button className={`btn btn-small${period === key ? " selected" : ""}`} key={key} aria-pressed={period === key} onClick={() => setPeriod(key)}>{label}</button>)}
      </div>
    </section>
    {([1, 2] as const).map((tier) => {
      const items = cards(tier);
      return items.length > 0 && <section key={tier} className="digest-section"><h2>{tier === 1 ? "Needs a look" : "Worth knowing"} ({items.length})</h2><ul>{items}</ul></section>;
    })}
    {activeCount === 0 && <p className="fine">{visible.length ? "Only routine filings in this view." : "No unseen filings in these stored records."}</p>}
    {cards(3).length > 0 && <details className="card digest-section"><summary>Routine ({cards(3).length})</summary><ul>{cards(3)}</ul></details>}
    {!!quiet.length && <p className="fine">Checked, no notices in the source response: {quiet.map((row) => row.symbol).join(", ")}.</p>}
    {unacknowledged.length > 0 && <button className="btn btn-primary" onClick={() => {
      updateVisit(markAll(visit.visit, candidates, digest.generated_at)); setPeriod("since");
    }}>Mark all as seen · {unacknowledged.length}</button>}
    {(!IS_STATIC || import.meta.env.VITE_LIVE_PRICES_URL) &&
      <details className="card"><summary>End-of-day flags</summary><LivePricesCard onOpenCompany={onOpenCompany} priceMovePct={5} volumeMultiple={2} /></details>}
    <div className="digest-actions"><a className="btn btn-small btn-ghost" href="#/?mode=replay">Historical replay</a>
      {!IS_STATIC && <a className="btn btn-small btn-ghost" href="#/?mode=live">Detailed filing filters</a>}</div>
  </div>;
}
