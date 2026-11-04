import { useCallback, useEffect, useRef, useState } from "react";
import { api, IS_STATIC, type Health, type ResearchMode } from "./api";
import { CompanyView } from "./CompanyView";
import { EvidenceSheet } from "./EvidenceSheet";
import { NarrativeView } from "./NarrativeView";
import { QueueView } from "./QueueView";
import { ResearchView } from "./ResearchView";
import { SavedResearch } from "./SavedResearch";
import { shortDate } from "./format";
import { StateBox } from "./ui";
import { CompanySearch } from "./CompanySearch";
import { NotebookProvider, NotebookSummary, NotebookView } from "./Notebook";
import { liveAppUrl, researchPath } from "./links";
import { ResearchModePicker } from "./ResearchModePicker";

type Route = (
  | { name: "queue" }
  | { name: "home" }
  | { name: "notebook" }
  | { name: "company"; symbol: string }
  | { name: "narrative"; symbol: string }
  | { name: "research"; symbol: string; jobId: string }) & { mode: ResearchMode; question?: string; eventId?: string };

function parse(hash: string): Route {
  const [path, query] = hash.replace(/^#\/?/, "").split("?", 2);
  const params = new URLSearchParams(query);
  const context = { mode: (params.get("mode") === "live" && !IS_STATIC ? "live" : "replay") as ResearchMode, question: params.get("question")?.slice(0, 300), eventId: params.get("event") || undefined };
  const parts = path.split("/").filter(Boolean).map((part) => { try { return decodeURIComponent(part); } catch { return part; } });
  if (parts[0] === "c" && parts[1] && parts[2] === "research" && parts[3]) return { ...context, name: "research", symbol: parts[1].toUpperCase(), jobId: parts[3] };
  if (parts[0] === "c" && parts[1] && parts[2] === "narrative") return { ...context, name: "narrative", symbol: parts[1].toUpperCase() };
  if (parts[0] === "c" && parts[1]) return { ...context, name: "company", symbol: parts[1].toUpperCase() };
  if (parts[0] === "research") return { ...context, name: "home" };
  if (parts[0] === "notebook") return { ...context, name: "notebook" };
  return { ...context, name: "queue" };
}

const go = (path: string, mode: ResearchMode = "replay") => { window.location.hash = path.includes("?") ? path : `${path}?mode=${mode}`; };

export function App() {
  return <NotebookProvider><AppShell /></NotebookProvider>;
}

function AppShell() {
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
  const retry = useCallback(async (symbol: string, eventId?: string | null, question?: string | null, mode: ResearchMode = "replay") => {
    const r = await api.research({ symbol, mode, event_id: eventId ?? undefined, question: question ?? undefined, retry: true });
    go(`/c/${encodeURIComponent(symbol)}/research/${encodeURIComponent(r.job_id)}`, mode);
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
  const tab = route.name === "queue" ? "review" : route.name === "notebook" ? "notebook" : "research";
  const setMode = (mode: ResearchMode) => route.name === "queue" ? go("/", mode) : go(researchPath({ symbol: "symbol" in route ? route.symbol : undefined, question: route.question, eventId: route.eventId, mode }));
  return (
    <div className="app">
      <header className="mode-banner" role="banner">
        <a href="#/" className="brand">FINN</a>
        {route.name === "notebook" ? <div className="mode"><strong>Your research workspace</strong><span>Saved privately in this browser</span></div> : route.mode === "live" ? <div className="mode"><strong>{route.name === "queue" ? "Current portfolio filings" : "Current-source research"}</strong><span>Source dates and coverage shown on each result</span></div> : replay ? (
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
          {" "}<a href={liveAppUrl({ mode: "live" })}>Open live research ↗</a> for new questions. The free service may take a minute to wake.
        </p>
      )}

        <nav className="tabs" aria-label="Primary">
          <a href={`#/?mode=${route.mode}`} aria-current={tab === "review" ? "page" : undefined} className={tab === "review" ? "active" : ""}>Review</a>
          <a href={`#/research?mode=${route.mode}`} aria-current={tab === "research" ? "page" : undefined} className={tab === "research" ? "active" : ""}>Research</a>
          <a href="#/notebook" aria-current={tab === "notebook" ? "page" : undefined} className={tab === "notebook" ? "active" : ""}>Notebook</a>
        </nav>

      <main className="main" aria-hidden={evidence ? true : undefined}>
        {healthError && <StateBox kind="error" title="FINN server unreachable" action={<button className="btn" onClick={loadHealth}>Retry</button>}>{healthError}</StateBox>}
        {busy && <StateBox kind="loading" title="Starting research…" />}
        {startError && <StateBox kind="error" title="Research could not start" action={<button className="btn btn-small" onClick={() => setStartError(null)}>Dismiss</button>}>{startError}</StateBox>}
        {route.name === "queue" && <QueueView key={route.mode} mode={route.mode} onMode={setMode} onOpenCompany={(s) => go(`/c/${encodeURIComponent(s)}`, route.mode)} onResearchEvent={route.mode === "replay" ? startResearch : async (symbol, eventId) => { try { const r = await api.research({ symbol, mode: "live", event_id: eventId }); go(`/c/${encodeURIComponent(symbol)}/research/${r.job_id}`, "live"); } catch (e) { setStartError(e instanceof Error ? e.message : "Research could not start."); } }} />}
        {route.name === "home" && <Home health={health} mode={route.mode} onMode={setMode} />}
        {route.name === "notebook" && <NotebookView />}
        {route.name === "company" && <CompanyView key={`${route.symbol}.${route.mode}.${route.question || ""}`} symbol={route.symbol} mode={route.mode} onMode={setMode} initialQuestion={route.question} initialEventId={route.eventId} onResearch={(id) => go(`/c/${encodeURIComponent(route.symbol)}/research/${id}`, route.mode)} onNarrative={() => go(`/c/${encodeURIComponent(route.symbol)}/narrative`, route.mode)} onEvidence={openEvidence} />}
        {route.name === "narrative" && <NarrativeView key={`${route.symbol}.${route.mode}`} symbol={route.symbol} mode={route.mode} onEvidence={openEvidence} onBack={() => go(`/c/${encodeURIComponent(route.symbol)}`, route.mode)} />}
        {route.name === "research" && <ResearchView key={route.jobId} jobId={route.jobId} onEvidence={openEvidence} onBack={() => go(`/c/${encodeURIComponent(route.symbol)}`, route.mode)} onRetry={retry} />}
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

function Home({ health, mode, onMode }: { health: Health | null; mode: ResearchMode; onMode: (mode: ResearchMode) => void }) {
  return (
    <div className="stack">
      <section className="card">
        <div className="eyebrow">Company research</div>
        <h1>Start with the source</h1>
        <p className="muted">Open a saved brief below, or find a company and ask a specific question. Every answer stays within its primary-source evidence.</p>
        {!IS_STATIC && <ResearchModePicker mode={mode} onChange={onMode} />}
        <CompanySearch mode={mode} />
      </section>
      <SavedResearch />
      <NotebookSummary />
      {health && (
        <section className="card">
          <h2>Source coverage</h2>
          <dl className="meta">
            <dt>Research</dt><dd>{IS_STATIC ? "Saved briefs and evidence are available here. New questions open in the live app." : health.model_configured ? "Cited AI research with a source-quote fallback. Source access is checked when you run a question." : "New questions return cited source quotes without a model key. Source access and coverage are shown with the result."}</dd>
            <dt>Stored sources</dt><dd>{health.corpus.documents} documents · {health.corpus.announcements} announcements · {health.corpus.eod_rows} daily prices</dd>
          </dl>
        </section>
      )}
    </div>
  );
}
