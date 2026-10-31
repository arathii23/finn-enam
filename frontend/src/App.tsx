import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Health } from "./api";
import { CompanyView } from "./CompanyView";
import { EvidenceSheet } from "./EvidenceSheet";
import { QueueView } from "./QueueView";
import { ResearchView } from "./ResearchView";
import { shortDate } from "./format";
import { StateBox } from "./ui";

type Route =
  | { name: "queue" }
  | { name: "home" }
  | { name: "company"; symbol: string }
  | { name: "research"; symbol: string; jobId: string };

function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "c" && parts[1] && parts[2] === "research" && parts[3]) return { name: "research", symbol: parts[1].toUpperCase(), jobId: parts[3] };
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
    setBusy(true);
    try {
      const r = await api.research({ symbol, mode: "replay", event_id: eventId });
      go(`/c/${symbol}/research/${r.job_id}`);
    } catch { go(`/c/${symbol}`); } finally { setBusy(false); }
  }, []);

  const replay = health?.replay;
  const tab = route.name === "home" ? "research" : route.name === "queue" ? "review" : null;
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
      </header>

      {tab && (
        <nav className="tabs" role="tablist" aria-label="Primary">
          <a href="#/" role="tab" aria-selected={tab === "review"} className={tab === "review" ? "active" : ""}>Review</a>
          <a href="#/research" role="tab" aria-selected={tab === "research"} className={tab === "research" ? "active" : ""}>Research</a>
        </nav>
      )}

      <main className="main" aria-hidden={evidence ? true : undefined}>
        {healthError && <StateBox kind="error" title="FINN server unreachable" action={<button className="btn" onClick={loadHealth}>Retry</button>}>{healthError}</StateBox>}
        {busy && <StateBox kind="loading" title="Starting research…" />}
        {route.name === "queue" && <QueueView onOpenCompany={(s) => go(`/c/${s}`)} onResearchEvent={startResearch} />}
        {route.name === "home" && <Home health={health} />}
        {route.name === "company" && <CompanyView key={route.symbol} symbol={route.symbol} onResearch={(id) => go(`/c/${route.symbol}/research/${id}`)} />}
        {route.name === "research" && <ResearchView key={route.jobId} jobId={route.jobId} onEvidence={openEvidence} onBack={() => go(`/c/${route.symbol}`)} onRetry={retry} />}
      </main>
      {evidence && <EvidenceSheet passageId={evidence} onClose={closeEvidence} />}
      <footer className="foot">Primary sources only: NSE records and company documents. No news, broker notes or model memory. Not investment advice.</footer>
    </div>
  );
}

function Home({ health }: { health: Health | null }) {
  const [symbol, setSymbol] = useState("");
  const prepared = health?.replay?.prepared_symbols ?? [];
  return (
    <div className="stack">
      <section className="card">
        <h1>Research a company</h1>
        <p className="muted">Enter any NSE symbol. FINN resolves its identity from the NSE security master and works only from documents that were public by the replay cutoff.</p>
        <form className="ticker" onSubmit={(e) => { e.preventDefault(); if (symbol.trim()) go(`/c/${symbol.trim().toUpperCase()}`); }}>
          <label htmlFor="sym" className="sr-only">NSE symbol</label>
          <input id="sym" value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="NSE symbol, e.g. INFY" autoCapitalize="characters" autoComplete="off" spellCheck={false} maxLength={20} />
          <button className="btn btn-primary" type="submit">Open</button>
        </form>
        {prepared.length > 0 && (
          <div className="prepared"><span className="fine">Prepared examples:</span>
            {prepared.map((s) => <a key={s} className="btn btn-small" href={`#/c/${s}`}>{s}</a>)}</div>
        )}
      </section>
      {health && (
        <section className="card">
          <h2>Server status</h2>
          <dl className="meta">
            <dt>Model</dt><dd>{health.model_configured ? `configured (${health.model_primary})` : "not configured: research shows passages without generated prose"}</dd>
            <dt>Corpus</dt><dd>{health.corpus.documents} documents · {health.corpus.passages} passages · {health.corpus.announcements} announcements · {health.corpus.eod_rows} EOD rows</dd>
          </dl>
        </section>
      )}
    </div>
  );
}
