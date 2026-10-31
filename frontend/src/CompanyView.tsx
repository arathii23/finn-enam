import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Announcement, type Overview } from "./api";
import { docLabel, host, inr, istDateTime, qty, shortDate } from "./format";
import { Chip, Section, StateBox } from "./ui";

type Props = { symbol: string; onResearch: (jobId: string) => void };

export function CompanyView({ symbol, onResearch }: Props) {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [starting, setStarting] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  const load = useCallback(() => {
    setData(null); setError(null);
    api.overview(symbol).then(setData).catch(setError);
  }, [symbol]);
  useEffect(load, [load]);

  async function start(event?: Announcement) {
    setStarting(event?.announcement_id ?? "company"); setStartError(null);
    try {
      const r = await api.research({
        symbol, mode: "replay", event_id: event?.announcement_id,
        question: event ? "What does this filing state, and what did management say around it?" : undefined,
      });
      onResearch(r.job_id);
    } catch (e) {
      setStartError((e as Error).message);
    } finally {
      setStarting(null);
    }
  }

  if (error) {
    const unknown = error.state === "unknown_symbol";
    return (
      <StateBox kind={unknown ? "empty" : "error"} title={unknown ? `Identity could not be resolved for “${symbol}”` : "Company could not be loaded"}
        action={<button className="btn" onClick={load}>Retry</button>}>
        {error.message}
      </StateBox>
    );
  }
  if (!data) return <StateBox kind="loading" title={`Resolving ${symbol} and loading its source inventory…`} />;

  const { company, announcements, eod, documents, coverage } = data;
  const failures = coverage.filter((c) => c.state !== "fetched");
  const notIngested = documents.eligible.length + documents.excluded.length === 0 && announcements.length === 0;

  return (
    <div className="stack">
      <section className="card identity">
        <div className="eyebrow">NSE · {company.series}</div>
        <h1>{company.legal_name}</h1>
        <div className="id-row"><span className="mono">{company.symbol}</span><span className="mono">ISIN {company.isin}</span></div>
        <p className="fine">Identity from the NSE equity security master ({host(company.identity_source_url)}, sha256:{company.identity_source_hash.slice(0, 10)}…).</p>
        <button className="btn btn-primary btn-block" onClick={() => start()} disabled={!!starting}>
          {starting === "company" ? "Starting research…" : "Research this company"}
        </button>
        {startError && <StateBox kind="error" title="Research could not start">{startError}</StateBox>}
      </section>

      {notIngested && (
        <StateBox kind="partial" title="Ready to find this company's sources">
          Select “Research this company” to find annual reports and call transcripts from dated exchange records. FINN will show which sources it can verify and any gaps.
        </StateBox>
      )}

      <Section title="Exchange announcements" aside={<Chip tone="muted">{announcements.length} in window</Chip>}>
        {announcements.length === 0 ? (
          <p className="muted">No announcements stored for the replay filing window. This is not an all-clear: check the source coverage below.</p>
        ) : (
          <ul className="list">
            {announcements.map((a) => (
              <li key={a.announcement_id} className="event">
                <div className="event-top">
                  <span className="event-cat">{a.category ?? "Uncategorised"}</span>
                  <time>{istDateTime(a.published_at)}</time>
                </div>
                <p className="event-subj">{a.subject}</p>
                <div className="event-actions">
                  {a.attachment_version_id ? (
                    <>
                      <Chip tone="ok">Filing retrieved</Chip>
                      <button className="btn btn-small" onClick={() => start(a)} disabled={!!starting}>
                        {starting === a.announcement_id ? "Starting…" : "Research this event"}
                      </button>
                      <a className="btn btn-small btn-ghost" href={api.fileUrl(a.attachment_version_id)} target="_blank" rel="noopener">Open filing</a>
                    </>
                  ) : (
                    <>
                      <Chip tone="muted">Metadata only</Chip>
                      {a.attachment_url && <a className="btn btn-small btn-ghost" href={a.attachment_url} target="_blank" rel="noopener noreferrer">Original attachment</a>}
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="End-of-day prices" aside={<Chip tone="muted">NSE daily file</Chip>}>
        {eod.length === 0 ? <p className="muted">No EOD rows stored for the replay window.</p> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th scope="col">Trading date</th><th scope="col">Close ₹</th><th scope="col">Prev ₹</th><th scope="col">Volume (shares)</th></tr></thead>
              <tbody>
                {eod.map((r) => (
                  <tr key={r.trading_date}><td>{shortDate(r.trading_date)}</td><td>{inr(r.close)}</td><td>{inr(r.prev_close)}</td><td>{qty(r.volume)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="fine">Raw exchange values, not adjusted. Trading dates are market sessions; filings published after the close do not explain that session's move.</p>
      </Section>

      <Section title="Primary documents" aside={<Chip tone="muted">{documents.eligible.length} eligible</Chip>}>
        <ul className="list">
          {documents.eligible.map((d) => (
            <li key={d.version_id} className="doc">
              <div><strong>{docLabel(d.doc_type, d.period_label)}</strong>
                <div className="sub">Published {istDateTime(d.published_at, d.published_precision)} · {d.page_count ?? "?"} pages · {d.parse_status}</div></div>
              <a className="btn btn-small btn-ghost" href={api.fileUrl(d.version_id)} target="_blank" rel="noopener">Open</a>
            </li>
          ))}
          {documents.excluded.map((d) => (
            <li key={d.version_id} className="doc excluded">
              <div><strong>{docLabel(d.doc_type, d.period_label)}</strong>
                <div className="sub">Excluded: {d.exclusion_reasons.join("; ")}{d.published_at ? ` · published ${istDateTime(d.published_at, d.published_precision)}` : ""}</div></div>
              <Chip tone="warn">Not used</Chip>
            </li>
          ))}
          {documents.eligible.length + documents.excluded.length === 0 && <li className="muted">No documents ingested.</li>}
        </ul>
      </Section>

      <Section title="Source coverage" aside={failures.length ? <Chip tone="warn">{failures.reduce((s, f) => s + f.n, 0)} not fetched</Chip> : <Chip tone="ok">All attempts fetched</Chip>}>
        <ul className="coverage">
          {coverage.map((c) => (
            <li key={c.source_kind + c.state}><span>{c.source_kind.replace(/_/g, " ").replace("document:", "doc: ")}</span>
              <span className={c.state === "fetched" ? "ok" : "warn"}>{c.state.replace(/_/g, " ")} × {c.n}</span></li>
          ))}
          {coverage.length === 0 && <li className="muted">No retrieval attempts recorded yet.</li>}
        </ul>
        <p className="fine">“not found” for a daily file means no report was published at that URL; it is not assumed to be a holiday.</p>
      </Section>
    </div>
  );
}
