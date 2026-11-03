import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, IS_STATIC, type LivePrices, type PortfolioQueue, type QueueCompany, type QueueEvent } from "./api";
import { shortDate } from "./format";
import { Chip, Section, StateBox } from "./ui";

const REVIEWED_KEY = "finn.reviewed.v1";
const PREFS_KEY = "finn.review.preferences.v2";
const SCROLL_KEY = "finn.review.scroll";
const CATEGORIES: Record<string, string> = {
  results: "Results", "M&A": "M&A", management_change: "Management", fund_raise: "Capital raising",
  litigation: "Regulatory / legal", credit_rating: "Credit rating", dividend: "Dividend",
  capex: "Capex", earnings_call: "Earnings calls", investor_meetings: "Investor meetings",
  press_release: "Company updates", agm_egm: "Shareholder meetings", pledging: "Promoter pledge",
  bonus_split: "Bonus / split", insider_trading: "Insider disclosures", unclassified: "Routine",
};
type Period = "24h" | "7d" | "all" | "custom";
type Preferences = { period: Period; price: string; vol: string; company: string; category: string; attention: string; from: string; to: string };
const DEFAULTS: Preferences = { period: "24h", price: "5", vol: "2", company: "all", category: "all", attention: "all", from: "", to: "" };
function stored<T extends object>(key: string, fallback: T): T {
  try { const value = JSON.parse(localStorage.getItem(key) || "null"); return value && typeof value === "object" && !Array.isArray(value) ? { ...fallback, ...value } : fallback; } catch { return fallback; }
}
function persist(key: string, value: unknown) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* local storage is optional */ } }
function readPreferences(): Preferences {
  const p = stored(PREFS_KEY, DEFAULTS);
  if (!["24h", "7d", "all", "custom"].includes(p.period) || (p.period === "custom" && (!p.from || !p.to))) p.period = "24h";
  for (const key of ["price", "vol"] as const) {
    if (p[key] == null || String(p[key]).trim() === "" || !Number.isFinite(Number(p[key])) || Number(p[key]) < 0 || Number(p[key]) > 100) p[key] = DEFAULTS[key];
  }
  return p;
}
function rememberScroll() { try { sessionStorage.setItem(SCROLL_KEY, String(window.scrollY)); } catch { /* optional */ } }
function fingerprint(c: QueueCompany): string {
  const ids = [...(c.leading_events || []), ...(c.notable_events || [])].map((e) => e.announcement_id).sort();
  return [...ids, ...(c.eod_anomaly?.flagged ? [c.eod_anomaly.trading_date, ...c.eod_anomaly.flags] : [])].join(",");
}
function eventTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }) + " IST" : "Date not supplied";
}
function headline(subject: string | null, fallback: string): string {
  const value = (subject || fallback).replace(/^.+?has informed the Exchange(?:\s+(?:that|regarding|about))?\s*/i, "").trim();
  return value ? value[0].toUpperCase() + value.slice(1) : fallback;
}

export function QueueView({ onOpenCompany, onResearchEvent }: {
  onOpenCompany: (symbol: string) => void;
  onResearchEvent: (symbol: string, eventId?: string) => void;
}) {
  const [prefs, setPrefs] = useState<Preferences>(readPreferences);
  const [data, setData] = useState<PortfolioQueue | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [reviewed, setReviewed] = useState<Record<string, string>>(() => stored(REVIEWED_KEY, {}));
  const [showReviewed, setShowReviewed] = useState(false);
  const request = useRef(0);
  const restored = useRef(false);
  const initial = useRef(prefs);
  const update = (next: Partial<Preferences>) => setPrefs((p) => ({ ...p, ...next }));
  useEffect(() => persist(PREFS_KEY, prefs), [prefs]);

  const load = useCallback((p: Preferences) => {
    const id = ++request.current;
    setError(null); setRefreshing(true);
    api.portfolio({ priceMovePct: Number(p.price), volumeMultiple: Number(p.vol), window: p.period,
      filingFrom: p.period === "custom" ? p.from : undefined, filingTo: p.period === "custom" ? p.to : undefined })
      .then((result) => { if (id === request.current) setData(result); })
      .catch((e) => { if (id === request.current) setError(e); })
      .finally(() => { if (id === request.current) setRefreshing(false); });
  }, []);
  useEffect(() => { load(initial.current); return () => { request.current++; }; }, [load]);
  useEffect(() => {
    if (!data || restored.current) return;
    restored.current = true;
    try { const y = Number(sessionStorage.getItem(SCROLL_KEY)); if (y > 0) requestAnimationFrame(() => window.scrollTo(0, y)); } catch { /* optional */ }
  }, [data]);

  const toggleReviewed = (c: QueueCompany) => {
    const next = { ...reviewed };
    if (next[c.symbol] === fingerprint(c)) delete next[c.symbol]; else next[c.symbol] = fingerprint(c);
    setReviewed(next); persist(REVIEWED_KEY, next);
  };
  const matches = (e: QueueEvent) => (prefs.category === "all" || e.ref_category === prefs.category) && (prefs.attention !== "leading" || e.tier === 1);
  const visible = (data?.companies ?? []).filter((c) => c.status === "ok" && (prefs.company === "all" || c.symbol === prefs.company)).map((c) => ({
    ...c, leading_events: (c.leading_events || []).filter(matches), notable_events: (c.notable_events || []).filter(matches),
    routine_events: (c.routine_events || []).filter(matches),
  })).filter((c) => prefs.attention === "flags" ? c.eod_anomaly?.flagged && (prefs.category === "all" || c.leading_events.length + c.notable_events.length + c.routine_events.length > 0) :
    c.leading_events.length + c.notable_events.length + c.routine_events.length > 0 || (prefs.category === "all" && prefs.attention === "all" && c.eod_anomaly?.flagged));
  const original = (c: QueueCompany) => data!.companies.find((r) => r.symbol === c.symbol)!;
  const isReviewed = (c: QueueCompany) => reviewed[c.symbol] != null && reviewed[c.symbol] === fingerprint(original(c));
  const active = visible.filter((c) => !isReviewed(c));
  const done = visible.filter(isReviewed);
  const openCompany = (s: string) => { rememberScroll(); onOpenCompany(s); };
  const research = (s: string, id?: string) => { rememberScroll(); onResearchEvent(s, id); };
  const preset = (period: Period) => {
    const next = { ...prefs, period, ...(period === "custom" ? {
      from: prefs.from || data?.window.filing_from || "", to: prefs.to || data?.window.filing_to || "",
    } : {}) };
    setPrefs(next);
    if (period !== "custom") load(next);
  };
  const clearFilters = () => update({ company: "all", category: "all", attention: "all" });
  const noData = data?.companies.filter((c) => c.status !== "ok") ?? [];

  if (!data && error) return <StateBox kind="error" title="Review could not be loaded" action={<><button className="btn" onClick={() => load(prefs)}>Retry</button><button className="btn" onClick={() => { setPrefs({ ...DEFAULTS }); load(DEFAULTS); }}>Reset review</button></>}>{error.message}</StateBox>;
  if (!data) return <StateBox kind="loading" title="Opening your portfolio review…" />;
  const eventCount = data.companies.reduce((n, c) => n + c.coverage.announcements, 0);
  const leadCount = data.companies.reduce((n, c) => n + (c.leading_events?.length || 0), 0);

  return <div className="stack">
    <section className="card review-intro">
      <div className="eyebrow">Portfolio intelligence</div>
      <div className="card-head"><h1>What needs your attention</h1><Chip tone="muted">{data.summary.companies} holdings</Chip></div>
      <p className="muted">{leadCount} leading filings · {data.summary.price_volume_flagged} EOD flags · {eventCount} filings stored in this period</p>
      <div className="period-options" aria-label="Review period">
        {(([["24h", "24 hours"], ["7d", "7 days"], ["all", "Full replay"], ["custom", "Choose dates"]] as const)
          .filter(([value]) => !IS_STATIC || value !== "custom")).map(([value, label]) =>
          <button key={value} className={`btn btn-small${prefs.period === value ? " selected" : ""}`} aria-pressed={prefs.period === value} disabled={refreshing} onClick={() => preset(value)}>{label}</button>)}
      </div>
      {!IS_STATIC && prefs.period === "custom" && <form className="review-dates" onSubmit={(e) => { e.preventDefault(); load(prefs); }}>
        <label>From<input type="date" required min={data.replay?.filing_from} max={data.replay?.filing_to} value={prefs.from} onChange={(e) => update({ from: e.target.value })} /></label>
        <label>To<input type="date" required min={prefs.from || data.replay?.filing_from} max={data.replay?.filing_to} value={prefs.to} onChange={(e) => update({ to: e.target.value })} /></label>
        <button className="btn btn-small" disabled={refreshing}>Apply dates</button>
      </form>}
      <p className="fine review-window">{data.window.label} · {data.window.filing_from && shortDate(data.window.filing_from)}{data.window.filing_from !== data.window.filing_to && ` – ${shortDate(data.window.filing_to)}`} · Stored historical data, not a live feed.</p>
      {refreshing && <p className="fine" role="status">Updating review…</p>}
      {error && <StateBox kind="error" title="Review could not update">{error.message} The previous period is still shown.</StateBox>}
      <details className="review-preferences">
        <summary>Attention thresholds · price {data.thresholds.price_move_pct}% / volume {data.thresholds.volume_multiple}×</summary>
        {IS_STATIC
          ? <p className="fine">Threshold tuning recomputes EOD anomalies on the live backend. This static snapshot shows the default {data.thresholds.price_move_pct}% price / {data.thresholds.volume_multiple}× volume flags.</p>
          : <form className="thresholds-form" onSubmit={(e) => { e.preventDefault(); load(prefs); }}>
              <label>Price move ≥ <input type="number" min="0" max="100" step="any" required inputMode="decimal" value={prefs.price} onChange={(e) => update({ price: e.target.value })} aria-label="price move percent" />%</label>
              <label>Volume ≥ <input type="number" min="0" max="100" step="any" required inputMode="decimal" value={prefs.vol} onChange={(e) => update({ vol: e.target.value })} aria-label="volume multiple" />×</label>
              <button className="btn btn-small" disabled={refreshing}>Apply thresholds</button>
            </form>}
        <p className="fine">In-app flags use the latest stored EOD session on or before {shortDate(data.window.filing_to)}, with raw prices and prior-session volume. No real-time notification delivery or causal link to a filing.</p>
      </details>
    </section>
    <section className="card review-filters" aria-label="Filter review">
      <details>
      <summary>Filter view · {visible.length} matching holdings</summary>
      <div className="review-selects">
        <label>Company<select aria-label="Company" value={prefs.company} onChange={(e) => update({ company: e.target.value })}><option value="all">All holdings</option>{data.companies.map((c) => <option key={c.symbol} value={c.symbol}>{c.symbol}</option>)}</select></label>
        <label>Filing type<select aria-label="Filing type" value={prefs.category} onChange={(e) => update({ category: e.target.value })}><option value="all">All types</option>{Object.entries(CATEGORIES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      </div>
      <div className="attention-options" aria-label="Attention filter">
        {[["all", "All activity"], ["leading", "Leading"], ["flags", "EOD flags"]].map(([value, label]) => <button key={value} className={`btn btn-small${prefs.attention === value ? " selected" : ""}`} aria-pressed={prefs.attention === value} onClick={() => update({ attention: value })}>{label}</button>)}
      </div>
      <p className="fine">{visible.length} matching holdings · {active.length} left to review <button className="btn btn-small btn-ghost" onClick={clearFilters}>Clear filters</button></p>
      </details>
      <p className="fine">{active.length} left to review{prefs.category !== "all" || prefs.company !== "all" || prefs.attention !== "all" ? " · Filters applied" : " · All filing types"}</p>
    </section>
    {active.length === 0 && <StateBox kind="empty" title={done.length ? "All matching holdings reviewed" : "No activity matches this view"}>{done.length ? "Your reviewed items remain available below." : "Try another period or clear the filters. This view describes stored records, not a fresh exchange check."}</StateBox>}
    {active.map((c) => <CompanyCard key={c.symbol} c={c} reviewed={false} onToggle={() => toggleReviewed(original(c))} onOpenCompany={openCompany} onResearchEvent={research} />)}
    {done.length > 0 && <Section title={`Reviewed (${done.length})`} aside={<button className="btn btn-small btn-ghost" aria-expanded={showReviewed} onClick={() => setShowReviewed(!showReviewed)}>{showReviewed ? "Hide reviewed" : "Show reviewed"}</button>}>
      {showReviewed ? done.map((c) => <CompanyCard key={c.symbol} c={c} reviewed onToggle={() => toggleReviewed(original(c))} onOpenCompany={openCompany} onResearchEvent={research} />) : <p className="muted">{done.map((c) => c.symbol).join(", ")}</p>}
    </Section>}
    {!IS_STATIC && <LivePricesCard />}
    <p className="fine review-coverage">{data.summary.checked}/{data.summary.companies} holdings have stored data. Metadata coverage does not mean every attachment has been read.</p>
    {noData.length > 0 && <Section title="Source coverage gaps"><p className="fine">No stored activity for these holdings. Open a company to inspect its source inventory.</p><div className="prepared">{noData.map((c) => <button className="btn btn-small" key={c.symbol} onClick={() => openCompany(c.symbol)}>{c.symbol}</button>)}</div></Section>}
  </div>;
}

function LivePricesCard() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<LivePrices | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const load = () => {
    setLoading(true); setError(null);
    api.livePrices().then(setData).catch((e: ApiError) => setError(e.message)).finally(() => setLoading(false));
  };
  const toggle = () => { const next = !open; setOpen(next); if (next && !data && !loading) load(); };
  const pct = (n: number | null | undefined) => (n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(1)}%`);
  return (
    <section className="card">
      <button className="btn btn-small btn-ghost" aria-expanded={open} onClick={toggle} style={{ padding: 0 }}>
        {open ? "▾" : "▸"} Live market snapshot · free Yahoo EOD
      </button>
      {open && (
        <div style={{ marginTop: "0.6rem" }}>
          <p className="fine" style={{ marginTop: 0 }}>Live end-of-day from Yahoo Finance (free, no key). Separate from the stored replay above; raw prices, a move is not attributed to any filing.</p>
          {loading && <p className="fine" role="status">Fetching live prices…</p>}
          {error && <StateBox kind="error" title="Live prices unavailable" action={<button className="btn btn-small" onClick={load}>Retry</button>}>{error}</StateBox>}
          {data && (
            <>
              <p className="fine">{data.summary.ok}/{data.summary.companies} live · {data.summary.flagged} flagged at {data.thresholds.price_move_pct}% / {data.thresholds.volume_multiple}×</p>
              <table className="eod-table"><thead><tr><th>Symbol</th><th>Close</th><th>Day</th><th>Vol×</th></tr></thead>
                <tbody>{data.companies.map((c) => (
                  <tr key={c.symbol} className={c.anomaly?.flagged ? "flagged-row" : ""}>
                    <td>{c.symbol}</td>
                    <td>{c.state === "ok" && c.latest ? `${c.latest.close.toFixed(1)}` : <span className="fine">{c.error || c.state}</span>}</td>
                    <td>{pct(c.anomaly?.price_move_pct)}</td>
                    <td>{c.anomaly?.volume_ratio != null ? `${c.anomaly.volume_ratio.toFixed(1)}×` : "—"}</td>
                  </tr>
                ))}</tbody>
              </table>
              <p className="fine">Retrieved {new Date(data.retrieved_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST · {data.companies.find((c) => c.currency)?.currency ?? "INR"}. {data.disclaimer}</p>
            </>
          )}
        </div>
      )}
    </section>
  );
}

function CompanyCard({ c, reviewed, onToggle, onOpenCompany, onResearchEvent }: {
  c: QueueCompany; reviewed: boolean; onToggle: () => void; onOpenCompany: (s: string) => void; onResearchEvent: (s: string, id?: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const [showRoutine, setShowRoutine] = useState(false);
  const events = [...(c.leading_events || []), ...(c.notable_events || [])];
  const routine = c.routine_events || [];
  const an = c.eod_anomaly;
  return <section className={`card queue-card${reviewed ? " reviewed" : ""}`}>
    <div className="card-head"><div><button className="company-link" onClick={() => onOpenCompany(c.symbol)}>{c.symbol} <span aria-hidden="true">↗</span></button><div className="sub">{c.legal_name}</div></div><Chip tone="muted">{events.length + routine.length} filing{events.length + routine.length === 1 ? "" : "s"}</Chip></div>
    {an?.flagged && <div className="eod-flag"><strong>EOD flag · {shortDate(an.trading_date)}</strong><span>{an.flags.join(" · ")}</span>{an.notes.length > 0 && <span className="fine">{an.notes.join(" · ")}</span>}</div>}
    {(showAll ? events : events.slice(0, 3)).map((e) => <EventRow key={e.announcement_id} e={e} symbol={c.symbol} onResearchEvent={onResearchEvent} />)}
    {events.length > 3 && <button className="btn btn-small btn-ghost" aria-expanded={showAll} onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer filings" : `Show ${events.length - 3} more filing${events.length - 3 === 1 ? "" : "s"}`}</button>}
    {routine.length > 0 && <><button className="btn btn-small btn-ghost routine-toggle" aria-expanded={showRoutine} onClick={() => setShowRoutine(!showRoutine)}>{showRoutine ? "Hide" : "Show"} {routine.length} routine filing{routine.length === 1 ? "" : "s"}</button>{showRoutine && routine.map((e) => <EventRow key={e.announcement_id} e={e} symbol={c.symbol} onResearchEvent={onResearchEvent} />)}</>}
    {events.length === 0 && routine.length === 0 && <p className="fine">No filings in this period; shown for the EOD flag above.</p>}
    <div className="event-actions queue-actions"><button className="btn btn-small btn-primary" onClick={() => onOpenCompany(c.symbol)}>Open company</button><button className="btn btn-small" onClick={onToggle}>{reviewed ? "Undo reviewed" : "Mark reviewed"}</button></div>
  </section>;
}

function EventRow({ e, symbol, onResearchEvent }: { e: QueueEvent; symbol: string; onResearchEvent: (s: string, id?: string) => void }) {
  const text = headline(e.subject, e.reason);
  return <div className="event queue-event">
    <div className="event-top"><span className={`priority-label priority-${e.tier}`}>{e.tier === 1 ? "Leading" : e.tier === 2 ? "Notable" : "Routine"} · {CATEGORIES[e.ref_category] || e.reason}</span><time dateTime={e.published_at || undefined}>{eventTime(e.published_at)}</time></div>
    <p className="queue-headline">{text.length > 220 ? text.slice(0, 220) + "…" : text}</p>
    {e.subject && <details className="original-description"><summary>Exchange description</summary><p>{e.subject}</p></details>}
    <div className="event-actions">
      {e.attachment_version_id ? <><a className="btn btn-small btn-ghost" href={api.fileUrl(e.attachment_version_id)} target="_blank" rel="noopener">Read filing</a><button className="btn btn-small btn-ghost" onClick={() => onResearchEvent(symbol, e.announcement_id)}>Research event</button></> : <><span className="fine">Metadata only</span>{e.attachment_url && /^https:\/\//i.test(e.attachment_url) && <a className="btn btn-small btn-ghost" href={e.attachment_url} target="_blank" rel="noopener noreferrer">Exchange attachment</a>}</>}
    </div>
  </div>;
}
