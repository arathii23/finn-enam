import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError, type PortfolioQueue, type QueueCompany, type QueueEvent } from "./api";
import { istDateTime } from "./format";
import { Chip, Section, StateBox } from "./ui";

const REVIEWED_KEY = "finn.reviewed.v1";

function loadReviewed(): Record<string, string> {
  try { return JSON.parse(localStorage.getItem(REVIEWED_KEY) || "{}"); } catch { return {}; }
}
function saveReviewed(map: Record<string, string>) {
  try { localStorage.setItem(REVIEWED_KEY, JSON.stringify(map)); } catch { /* storage may be unavailable */ }
}
// A company's review state is tied to the set of its current leading/notable events,
// so a later material filing reopens an item that was marked reviewed.
function fingerprint(c: QueueCompany): string {
  const ids = [...(c.leading_events || []), ...(c.notable_events || [])].map((e) => e.announcement_id).sort();
  return ids.join(",");
}

const TIER_TONE: Record<number, "warn" | "neutral" | "muted"> = { 1: "warn", 2: "neutral", 3: "muted" };

export function QueueView({ onOpenCompany, onResearchEvent }: {
  onOpenCompany: (symbol: string) => void;
  onResearchEvent: (symbol: string, eventId?: string) => void;
}) {
  const [data, setData] = useState<PortfolioQueue | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [price, setPrice] = useState("5");
  const [vol, setVol] = useState("2");
  const [reviewed, setReviewed] = useState<Record<string, string>>(loadReviewed);
  const [showReviewed, setShowReviewed] = useState(false);

  const load = useCallback((p?: number, v?: number) => {
    setData(null); setError(null);
    api.portfolio({ priceMovePct: p, volumeMultiple: v }).then(setData).catch(setError);
  }, []);
  useEffect(() => { load(); }, [load]);

  const toggleReviewed = (c: QueueCompany) => {
    const next = { ...reviewed };
    if (next[c.symbol]) delete next[c.symbol]; else next[c.symbol] = fingerprint(c);
    setReviewed(next); saveReviewed(next);
  };
  const isReviewed = (c: QueueCompany) => reviewed[c.symbol] != null && reviewed[c.symbol] === fingerprint(c);

  const ok = data?.companies.filter((c) => c.status === "ok") ?? [];
  const noData = data?.companies.filter((c) => c.status !== "ok") ?? [];
  const active = useMemo(() => ok.filter((c) => !isReviewed(c)), [ok, reviewed]);
  const done = useMemo(() => ok.filter((c) => isReviewed(c)), [ok, reviewed]);

  if (error) return <StateBox kind="error" title="Review queue could not be loaded" action={<button className="btn" onClick={() => load()}>Retry</button>}>{error.message}</StateBox>;
  if (!data) return <StateBox kind="loading" title="Checking filings across your portfolio…" />;

  const s = data.summary;
  const applyThresholds = (e: React.FormEvent) => {
    e.preventDefault();
    load(Number(price) || undefined, Number(vol) || undefined);
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="card-head"><h1>Review</h1><Chip tone="muted">{s.checked} of {s.companies} checked</Chip></div>
        <p className="fine">What changed across your holdings, prioritised. Routine compliance filings are collapsed. {s.price_volume_flagged > 0 ? `${s.price_volume_flagged} with an unusual EOD move.` : "No unusual EOD moves at the threshold."}</p>
        <form className="thresholds-form" onSubmit={applyThresholds}>
          <label>Price move ≥ <input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} aria-label="price move percent" />%</label>
          <label>Volume ≥ <input inputMode="decimal" value={vol} onChange={(e) => setVol(e.target.value)} aria-label="volume multiple" />×</label>
          <button className="btn btn-small" type="submit">Apply</button>
        </form>
        <p className="fine">EOD checks are end-of-day, raw (unadjusted); a move is not attributed to any filing.</p>
      </section>

      {active.length === 0 && <StateBox kind="empty" title="Nothing left to review">All holdings with activity have been marked reviewed.</StateBox>}

      {active.map((c) => (
        <CompanyCard key={c.symbol} c={c} reviewed={false} onToggle={() => toggleReviewed(c)}
                     onOpenCompany={onOpenCompany} onResearchEvent={onResearchEvent} />
      ))}

      {done.length > 0 && (
        <Section title={`Reviewed (${done.length})`} aside={<button className="btn btn-small btn-ghost" onClick={() => setShowReviewed(!showReviewed)}>{showReviewed ? "Hide" : "Show"}</button>}>
          {showReviewed ? done.map((c) => (
            <CompanyCard key={c.symbol} c={c} reviewed onToggle={() => toggleReviewed(c)}
                         onOpenCompany={onOpenCompany} onResearchEvent={onResearchEvent} />
          )) : <p className="muted">{done.map((c) => c.symbol).join(", ")}</p>}
        </Section>
      )}

      {noData.length > 0 && (
        <Section title={`Not yet ingested (${noData.length})`} aside={<Chip tone="muted">coverage gap</Chip>}>
          <p className="fine">These holdings resolve to an NSE identity but have no ingested filings/EOD yet. Run ingestion on a networked machine: <code>python -m finn ingest {noData.slice(0, 2).map((c) => c.symbol).join(" ")} …</code></p>
          <div className="prepared">{noData.map((c) => (
            <button key={c.symbol} className="btn btn-small btn-ghost" onClick={() => onOpenCompany(c.symbol)}>{c.symbol}</button>
          ))}</div>
        </Section>
      )}
    </div>
  );
}

function CompanyCard({ c, reviewed, onToggle, onOpenCompany, onResearchEvent }: {
  c: QueueCompany; reviewed: boolean; onToggle: () => void;
  onOpenCompany: (s: string) => void; onResearchEvent: (s: string, id?: string) => void;
}) {
  const [showRoutine, setShowRoutine] = useState(false);
  const an = c.eod_anomaly;
  return (
    <section className={`card queue-card${reviewed ? " reviewed" : ""}`}>
      <div className="card-head">
        <div>
          <strong className="queue-sym">{c.symbol}</strong>
          <div className="sub">{c.legal_name}</div>
        </div>
        {an?.flagged && <Chip tone="warn">EOD {an.price_move_pct != null ? `${an.price_move_pct > 0 ? "+" : ""}${an.price_move_pct}%` : "move"}{an.volume_ratio != null ? ` · ${an.volume_ratio}× vol` : ""}</Chip>}
      </div>

      {(c.leading_events || []).map((e) => <EventRow key={e.announcement_id} e={e} symbol={c.symbol} onResearchEvent={onResearchEvent} lead />)}
      {(c.notable_events || []).map((e) => <EventRow key={e.announcement_id} e={e} symbol={c.symbol} onResearchEvent={onResearchEvent} />)}
      {(c.leading_events?.length || 0) + (c.notable_events?.length || 0) === 0 && (
        <p className="muted">No material or notable filings in this window.</p>
      )}

      {(c.routine_count || 0) > 0 && (
        <button className="btn btn-small btn-ghost routine-toggle" onClick={() => setShowRoutine(!showRoutine)}>
          {showRoutine ? "Hide" : "Show"} {c.routine_count} routine filing{c.routine_count === 1 ? "" : "s"}
        </button>
      )}
      {showRoutine && <p className="fine">Routine compliance/paperwork (newspaper copies, share-certificate losses, ESOP allotments, trading-window notices). Open the company to see the full chronological list.</p>}

      <div className="event-actions">
        {c.can_research && <button className="btn btn-small btn-primary" onClick={() => onResearchEvent(c.symbol)}>Research</button>}
        <button className="btn btn-small" onClick={() => onOpenCompany(c.symbol)}>Open company</button>
        <button className={`btn btn-small${reviewed ? " btn-ghost" : ""}`} onClick={onToggle}>{reviewed ? "Reviewed ✓ (undo)" : "Mark reviewed"}</button>
      </div>
    </section>
  );
}

function EventRow({ e, symbol, onResearchEvent, lead }: { e: QueueEvent; symbol: string; onResearchEvent: (s: string, id?: string) => void; lead?: boolean }) {
  return (
    <div className="event">
      <div className="event-top">
        <span className="event-cat">{lead && <Chip tone={TIER_TONE[e.tier]}>{e.ref_category}</Chip>} {e.reason}</span>
        <time>{istDateTime(e.published_at)}</time>
      </div>
      {e.subject && <p className="event-subj">{e.subject}</p>}
      <div className="event-actions">
        {e.attachment_version_id && <a className="btn btn-small btn-ghost" href={api.fileUrl(e.attachment_version_id)} target="_blank" rel="noopener">Open filing</a>}
        {e.attachment_version_id && <button className="btn btn-small btn-ghost" onClick={() => onResearchEvent(symbol, e.announcement_id)}>Research this event</button>}
      </div>
    </div>
  );
}
