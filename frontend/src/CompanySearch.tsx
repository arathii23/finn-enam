import { useEffect, useState } from "react";
import { api, IS_STATIC, type QueueCompany, type ResearchMode } from "./api";
import { liveAppUrl, researchPath } from "./links";

const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

export function CompanySearch({ mode }: { mode: ResearchMode }) {
  const [query, setQuery] = useState("");
  const [companies, setCompanies] = useState<QueueCompany[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { let active = true; api.portfolio({ window: "all" }).then((data) => { if (active) setCompanies(data.companies); }).catch(() => { /* The direct symbol entry remains available. */ }); return () => { active = false; }; }, []);
  const needle = normalize(query);
  const matches = companies.filter((company) => !needle || normalize(`${company.symbol} ${company.legal_name || ""}`).includes(needle));
  const open = (symbol: string) => { window.location.hash = researchPath({ symbol, mode }); };
  return <div className="company-search">
    <form className="ticker" onSubmit={(event) => {
      event.preventDefault(); setError(null);
      const exact = companies.find((company) => normalize(company.symbol) === needle || normalize(company.legal_name || "") === needle);
      if (exact) return open(exact.symbol);
      if (matches.length === 1) return open(matches[0].symbol);
      if (/^[A-Za-z0-9&._\-]{1,20}$/.test(query.trim())) return open(query.trim().toUpperCase());
      setError("Choose a matching company below, or enter its NSE symbol.");
    }}>
      <label className="sr-only" htmlFor="company-search">Company name or NSE symbol</label>
      <input id="company-search" value={query} onChange={(event) => { setQuery(event.target.value); setError(null); }} placeholder="Company name or NSE symbol" autoComplete="off" spellCheck={false} maxLength={80} required />
      <button className="btn btn-primary">Open</button>
    </form>
    {error && <p className="composer-error" role="alert">{error}</p>}
    <p className="fine">{IS_STATIC ? "Browse the 15 companies in this snapshot. Other NSE symbols can be researched in the live app." : "Search the portfolio by name or symbol, or enter another NSE symbol to find its primary sources."}</p>
    {companies.length > 0 && <ul className="company-results" aria-label="Matching portfolio companies">{(showAll || needle ? matches : matches.slice(0, 5)).map((company) => <li key={company.symbol}><button className="company-result" onClick={() => open(company.symbol)}><strong>{company.symbol}</strong><span>{company.legal_name || company.symbol}</span><span className="sub">{company.coverage.documents} stored documents</span></button></li>)}</ul>}
    {!needle && companies.length > 5 && <button className="btn btn-small btn-ghost" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer companies" : `Browse all ${companies.length} holdings`}</button>}
    {IS_STATIC && needle && matches.length === 0 && <div className="live-handoff"><p className="fine">This company is outside the saved snapshot.</p><a className="btn btn-small" href={liveAppUrl({ symbol: /^[A-Za-z0-9&._\-]{1,20}$/.test(query.trim()) ? query.trim() : undefined, mode: "live" })}>Find current sources in live app ↗</a></div>}
  </div>;
}
