import { useCallback, useEffect, useRef, useState } from "react";
import { api, IS_STATIC, type Health } from "./api";
import { CompanyView } from "./CompanyView";
import { EvidenceSheet } from "./EvidenceSheet";
import { NarrativeView } from "./NarrativeView";
import { QueueView } from "./QueueView";
import { ResearchView } from "./ResearchView";
import { SavedResearch } from "./SavedResearch";
import { shortDate } from "./format";
import { StateBox } from "./ui";

type Route =
  | { name: "queue" }
  | { name: "home" }
  | { name: "company"; symbol: string }
  | { name: "narrative"; symbol: string }
  | { name: "research"; symbol: string; jobId: string };

function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map((part) => { try { return decodeURIComponent(part); } catch { return part; } });
  if (parts[0] === "c" && parts[1] && parts[2] === "research" && parts[3]) return { name: "research", symbol: parts[1].toUpperCase(), jobId: parts[3] };
  if (parts[0] === "c" && parts[1] && parts[2] === "narrative") return { name: "narrative", symbol: parts[1].toUpperCase() };
  if (parts[0] === "c" && parts[1]) return { name: "company", symbol: parts[1].toUpperCase() };
  if (parts[0] === "research") return { name: "home" };
  return { name: "queue" };
}

const go = (path: string) => { window.location.hash = path; };

export function App() {
  const [route, setRoute] = useState<Route>(parse(window.location.hash));
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const starting = useRef(false);
  const returnFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const onHash = () => { setRoute(parse(window.location.hash)); setEvidence(null); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const loadHealth = useCallback(() => {
    setHealthError(null);
    api.health().then(setHealth).catch((e) => setHealthError(e.message));
  }, []);
  useEffect(loadHealth, [loadHealth]);

  const openEvidence = useCallback((id: string, el: HTMLElement) => { returnFocus.current = el; setEvidence(id); }, []);
  const closeEvidence = useCallback(() => { setEvidence(null); window.setTimeout(() => returnFocus.current?.focus(), 0); }, []);
  const retry = useCallback(async (symbol: string, eventId?: string | null, question?: string | null) => {
    const r = await api.research({ symbol, mode: "replay", event_id: eventId ?? undefined, question: question ?? undefined, retry: true });
    go(`/c/${symbol}/research/${r.job_id}`);
  }, []);
  const startResearch = useCallback(async (symbol: string, eventId?: string) => {
    if (starting.current) return;
    starting.current = true;
    setBusy(true); setStartError(null);
    try {
      const r = await api.research({ symbol, mode: "replay", event_id: eventId });
      go(`/c/${symbol}/research/${r.job_id}`);
    } catch (e) { setStartError(e instanceof Error ? e.message : "Research could not start. Please try again."); }
    finally { starting.current = false; setBusy(false); }
  }, []);

  const replay = health?.replay;
  const tab = route.name === "queue" ? "review" : "research";
  return (
    <div className="app">
      <header className="mode-banner" role="banner">
        <a href="#/" className="brand">FINN</a>
        {replay ? (
          <div className="mode">
            <strong>{replay.label}</strong>
            <span>Filings {shortDate(replay.filing_from)} – {shortDate(replay.filing_to)}</span>
            <span>Evidence by {replay.cutoff_display}</span>
          </div>
        ) : <div className="mode"><strong>Mode unknown</strong><span>{healthError ? "server unreachable" : "loading…"}</span></div>}
        <ShareButton />
      </header>
      {IS_STATIC && (
        <p className="snapshot-note" role="note">
          Read-only snapshot · browse the Push digest, saved research briefs and primary-source evidence.
          On-demand research runs on the live backend.
        </p>
      )}

        <nav className="tabs" aria-label="Primary">
          <a href="#/" aria-current={tab === "review" ? "page" : undefined} className={tab === "review" ? "active" : ""}>Review</a>
          <a href="#/research" aria-current={tab === "research" ? "page" : undefined} className={tab === "research" ? "active" : ""}>Research</a>
        </nav>

      <main className="main" aria-hidden={evidence ? true : undefined}>
        {healthError && <StateBox kind="error" title="FINN server unreachable" action={<button className="btn" onClick={loadHealth}>Retry</button>}>{healthError}</StateBox>}
        {busy && <StateBox kind="loading" title="Starting research…" />}
        {startError && <StateBox kind="error" title="Research could not start" action={<button className="btn btn-small" onClick={() => setStartError(null)}>Dismiss</button>}>{startError}</StateBox>}
        {route.name === "queue" && <QueueView onOpenCompany={(s) => go(`/c/${s}`)} onResearchEvent={startResearch} />}
        {route.name === "home" && <Home health={health} />}
        {route.name === "company" && <CompanyView key={route.symbol} symbol={route.symbol} onResearch={(id) => go(`/c/${route.symbol}/research/${id}`)} onNarrative={() => go(`/c/${route.symbol}/narrative`)} onEvidence={openEvidence} />}
        {route.name === "narrative" && <NarrativeView key={route.symbol} symbol={route.symbol} onEvidence={openEvidence} onBack={() => go(`/c/${route.symbol}`)} />}
        {route.name === "research" && <ResearchView key={route.jobId} jobId={route.jobId} onEvidence={openEvidence} onBack={() => go(`/c/${route.symbol}`)} onRetry={retry} />}
      </main>
      {evidence && <EvidenceSheet passageId={evidence} onClose={closeEvidence} />}
      <footer className="foot">Primary sources only: NSE records and company documents. No news, broker notes or model memory. Not investment advice.</footer>
    </div>
  );
}

function ShareButton() {
  const [copied, setCopied] = useState(false);
  const share = async () => {
    const url = window.location.href;
    const data = { title: "FINN — primary-source investor research", url };
    try {
      if (navigator.share) { await navigator.share(data); return; }
    } catch { /* user dismissed the share sheet; fall through to copy */ }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true); window.setTimeout(() => setCopied(false), 2000);
    } catch { window.prompt("Copy this link to share FINN:", url); }
  };
  return <button type="button" className="share-btn" onClick={share} aria-label="Share this view">
    {copied ? "Link copied" : "Share"}
  </button>;
}

function Home({ health }: { health: Health | null }) {
  const [symbol, setSymbol] = useState("");
  return (
    <div className="stack">
      <section className="card">
        <div className="eyebrow">Company research</div>
        <h1>Start with the source</h1>
        <p className="muted">Open a saved brief below, or find a company and ask a specific question. Every answer stays within its primary-source evidence.</p>
        <form className="ticker" onSubmit={(e) => { e.preventDefault(); if (symbol.trim()) go(`/c/${encodeURIComponent(symbol.trim().toUpperCase())}`); }}>
          <label htmlFor="sym" className="sr-only">NSE symbol</label>
          <input id="sym" value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="NSE symbol, e.g. INFY" autoCapitalize="characters" autoComplete="off" spellCheck={false} maxLength={20} pattern="[A-Za-z0-9&._\-]+" required />
          <button className="btn btn-primary" type="submit">Open</button>
        </form>
      </section>
      <SavedResearch />
      {health && (
        <section className="card">
          <h2>Source coverage</h2>
          <dl className="meta">
            <dt>Research</dt><dd>{health.model_configured ? "New briefs can be requested. Source access and service availability are checked when you run a question." : "Saved results and source passages available; new summaries are unavailable"}</dd>
            <dt>Stored sources</dt><dd>{health.corpus.documents} documents · {health.corpus.announcements} announcements · {health.corpus.eod_rows} daily prices</dd>
          </dl>
        </section>
      )}
    </div>
  );
}
