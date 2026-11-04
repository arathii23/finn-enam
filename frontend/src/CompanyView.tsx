import { useCallback, useEffect, useState } from "react";
import { api, ApiError, IS_STATIC, type Announcement, type Overview, type Quarterly, type ResearchMode } from "./api";
import { docLabel, inr, istDateTime, qty, shortDate } from "./format";
import { Chip, EvidenceButton, Section, StateBox } from "./ui";
import { ManagementCard } from "./ManagementCard";
import { ResearchComposer } from "./ResearchComposer";
import { SavedResearch } from "./SavedResearch";
import { liveAppUrl } from "./links";
import { ResearchModePicker } from "./ResearchModePicker";

type Props = { symbol: string; mode: ResearchMode; onMode: (mode: ResearchMode) => void; initialQuestion?: string; initialEventId?: string; onResearch: (jobId: string) => void; onNarrative: () => void; onEvidence: (id: string, el: HTMLElement) => void };

export function CompanyView({ symbol, mode, onMode, initialQuestion, initialEventId, onResearch, onNarrative, onEvidence }: Props) {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [starting, setStarting] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  const load = useCallback(() => {
    setData(null); setError(null);
    api.overview(symbol, mode).then(setData).catch(setError);
  }, [symbol, mode]);
  useEffect(load, [load]);

  async function start(event?: Announcement, question?: string) {
    setStarting(event?.announcement_id ?? "company"); setStartError(null);
    try {
      const r = await api.research({
        symbol, mode, event_id: event?.announcement_id,
        question: question ?? (event ? "What does this filing state, and what did management say around it?" : undefined),
      });
      onResearch(r.job_id);
    } catch (e) {
      setStartError((e as Error).message);
      if (question) throw e;
    } finally {
      setStarting(null);
    }
  }

  if (error) {
    const unknown = error.state === "unknown_symbol";
    return (
      <StateBox kind={unknown ? "empty" : "error"} title={unknown ? `Identity could not be resolved for “${symbol}”` : "Company could not be loaded"}
        action={IS_STATIC && error.state === "not_in_snapshot" ? <a className="btn" href={liveAppUrl({ symbol, question: initialQuestion, eventId: initialEventId, mode: "live" })}>Find sources in live app ↗</a> : <button className="btn" onClick={load}>Retry</button>}>
        {error.message}
      </StateBox>
    );
  }
  if (!data) return <StateBox kind="loading" title={`Resolving ${symbol} and loading its source inventory…`} />;

  const { company, announcements, eod, documents, coverage } = data;
  const hasNarrative = documents.eligible.some((d) => d.doc_type === "earnings_call_transcript" || d.doc_type === "exchange_filing");
  const attemptCount = coverage.reduce((sum, item) => sum + item.n, 0);
  const notIngested = documents.eligible.length + documents.excluded.length === 0 && announcements.length === 0;
  const contextualEvent = initialEventId ? announcements.find((event) => event.announcement_id === initialEventId) : undefined;

  return (
    <div className="stack">
      <section className="card identity">
        <div className="eyebrow">NSE · {company.series}</div>
        <h1>{company.legal_name}</h1>
        <div className="id-row"><span className="mono">{company.symbol}</span><span className="mono">ISIN {company.isin}</span></div>
        <p className="fine">Identity verified against the NSE equity security master.</p>
        {!IS_STATIC && <ResearchModePicker mode={mode} onChange={onMode} />}
        {mode === "live" && <div className="source-freshness" role="note"><strong>Stored source coverage</strong><p className="fine">Latest publication: {data.freshness?.latest_publication ? istDateTime(data.freshness.latest_publication) : "not established"}. Last source check: {data.freshness?.last_checked ? istDateTime(data.freshness.last_checked) : "not recorded"}.</p><p className="fine">{data.freshness?.note || "Research checks for current documents. Stored dates alone do not establish complete or current coverage."}</p></div>}
        {IS_STATIC ? <a className="btn btn-primary btn-block" href={liveAppUrl({ symbol, question: initialQuestion, eventId: initialEventId, mode })}>Research in live app ↗</a> : <button className="btn btn-primary btn-block" onClick={() => start(contextualEvent, initialQuestion)} disabled={!!starting}>
          {starting ? "Starting research…" : initialQuestion ? "Run this question" : mode === "live" ? "Check current sources & research" : "Research this company"}
        </button>}
        {IS_STATIC && <p className="fine">Saved briefs below open immediately. New questions open in the live app; its free service may take a minute to wake.</p>}
        {hasNarrative && (
          <button className="btn btn-block nv-entry" onClick={onNarrative} disabled={!!starting}>
            Numbers vs Narrative — promised vs delivered →
          </button>
        )}
        {startError && <StateBox kind="error" title="Research could not start">{startError}</StateBox>}
      </section>

      <SavedResearch symbol={symbol} />
      <ResearchComposer busy={!!starting} initialQuestion={initialQuestion} symbol={symbol} company={company.legal_name} mode={mode} cutoff={data.replay?.cutoff_utc} eventId={contextualEvent?.announcement_id} onSubmit={(question) => start(contextualEvent, question)} />

      {notIngested && (
        <StateBox kind="partial" title="Ready to find this company's sources">
          {IS_STATIC ? "Open the live app to find primary documents for this company." : "Select Research to find annual reports and call transcripts from dated exchange records. FINN will show which sources it can verify and any gaps."}
        </StateBox>
      )}

      {hasNarrative && <ManagementCard symbol={symbol} mode={mode} onEvidence={onEvidence} />}
      {hasNarrative && <QuarterlyCard symbol={symbol} mode={mode} onEvidence={onEvidence} />}

      <Section title="Exchange announcements" aside={<Chip tone="muted">{announcements.length} in window</Chip>}>
        {announcements.length === 0 ? (
          <p className="muted">No announcements stored for this {mode === "replay" ? "replay window" : "source view"}. This is not an all-clear: check the source coverage below.</p>
        ) : (
          <details className="research-disclosure">
          <summary>View {announcements.length} filings in date order</summary>
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
                      {IS_STATIC ? <a className="btn btn-small" href={liveAppUrl({ symbol, eventId: a.announcement_id, question: "What does this filing state, and what did management say around it?", mode })}>Research event in live app ↗</a> : <button className="btn btn-small" onClick={() => start(a)} disabled={!!starting}>
                        {starting === a.announcement_id ? "Starting…" : "Research this event"}
                      </button>}
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
          </details>
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
        <details className="research-disclosure">
        <summary>Inspect eligible and excluded documents</summary>
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
        </details>
      </Section>

      <Section title="Retrieval history" aside={<Chip tone="muted">{attemptCount} recorded attempts</Chip>}>
        <p className="fine">Past retrieval attempts, including shared exchange requests. Earlier failures do not establish whether a document is available now.</p>
        <details className="research-disclosure">
        <summary>View retrieval history</summary>
        <ul className="coverage">
          {coverage.map((c) => (
            <li key={c.source_kind + c.state}><span>{c.source_kind.replace(/_/g, " ").replace("document:", "doc: ")}</span>
              <span className={c.state === "fetched" ? "ok" : "warn"}>{c.state.replace(/_/g, " ")} × {c.n}</span></li>
          ))}
          {coverage.length === 0 && <li className="muted">No retrieval attempts recorded yet.</li>}
        </ul>
        <p className="fine">“not found” for a daily file means no report was published at that URL; it is not assumed to be a holiday.</p>
        </details>
      </Section>
    </div>
  );
}

function pctText(v: number | null): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

// Quarterly first cut (Push): headline Revenue / EBITDA / PBT / PAT with QoQ & YoY from the
// actual results filing. Model-extracted, then every figure verified verbatim against the filing;
// anything that cannot be verified is omitted, not guessed.
function QuarterlyCard({ symbol, mode, onEvidence }: { symbol: string; mode: ResearchMode; onEvidence: (id: string, el: HTMLElement) => void }) {
  const [q, setQ] = useState<Quarterly | null>(null);
  const [err, setErr] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setQ(null); setErr(false);
    api.quarterly(symbol, mode).then((r) => live && setQ(r)).catch(() => live && setErr(true));
    return () => { live = false; };
  }, [symbol, mode, attempt]);

  const extract = async () => {
    setExtracting(true); setExtractError(null);
    try { setQ(await api.extractQuarterly(symbol, mode)); }
    catch (error) { setExtractError(error instanceof Error ? error.message : "Headline figures could not be extracted."); }
    finally { setExtracting(false); }
  };

  if (err) return <Section title="Quarterly first cut"><p className="muted">Results could not be loaded.</p><button className="btn btn-small" onClick={() => setAttempt(attempt + 1)}>Retry</button></Section>;
  if (!q) return <Section title="Quarterly first cut"><p className="muted">Reading the results filing…</p></Section>;
  if (!q.available) {
    return (
      <Section title="Quarterly first cut" aside={<Chip tone="muted">not available</Chip>}>
        <p className="muted">{q.reason ?? "No headline numbers could be verified from this filing."}</p>
        <p className="fine">FINN omits figures it cannot verify against the filing rather than guessing.</p>
        {q.can_extract && (IS_STATIC ? <a className="btn btn-small" href={liveAppUrl({ symbol, mode })}>Inspect figures in live app ↗</a> : <button className="btn btn-small" disabled={extracting} onClick={extract}>{extracting ? "Reading the filing…" : "Extract headline figures"}</button>)}
        {q.can_extract && !IS_STATIC && <p className="fine">Starts one bounded extraction from the results filing. Opening this page does not run a model.</p>}
        {extractError && <p className="composer-error" role="alert">{extractError}</p>}
      </Section>
    );
  }
  const cols = q.columns!;
  return (
    <Section title={`Quarterly first cut · ${cols.current ?? ""}`} aside={q.basis ? <Chip tone="muted">{q.basis}</Chip> : undefined}>
      <div className="table-wrap">
        <table className="qtable">
          <thead><tr><th scope="col">Metric</th><th scope="col">This quarter</th><th scope="col">QoQ</th><th scope="col">YoY</th></tr></thead>
          <tbody>
            {q.metrics!.map((m) => (
              <tr key={m.key}>
                <th scope="row" className="qmetric">{m.label}
                  {m.evidence_id && <div className="q-row-source"><EvidenceButton id={m.evidence_id} label={`Source${m.source ? ` · PDF p.${m.source.page_index}` : ""}`} onOpen={onEvidence} /></div>}
                </th>
                <td className="qval">{m.current.value_text}<span className="sub">{m.unit || "Unit not identified"}</span></td>
                <td className="qdelta">{pctText(m.qoq_pct)}</td>
                <td className="qdelta">{pctText(m.yoy_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="fine">{q.basis ? `${q.basis[0].toUpperCase()}${q.basis.slice(1)} basis. ` : ""}
        QoQ vs {cols.previous_quarter ?? "prior quarter"} · YoY vs {cols.year_ago_quarter ?? "year-ago quarter"}.
        {q.metrics!.some((m) => m.qoq_pct == null) && " Some comparatives are shown only where the filing stated that period."}</p>
      <details className="research-disclosure">
        <summary>Compare the reported values</summary>
        <div className="table-wrap">
          <table className="qtable q-comparison">
            <caption>Values as stated in the filing; units are shown with each metric.</caption>
            <thead><tr><th scope="col">Metric</th><th scope="col">{cols.current ?? "This quarter"}</th><th scope="col">{cols.previous_quarter ?? "Previous quarter"}</th><th scope="col">{cols.year_ago_quarter ?? "Year-ago quarter"}</th></tr></thead>
            <tbody>{q.metrics!.map((m) => (
              <tr key={m.key}><th scope="row" className="qmetric">{m.label}<span className="sub">{m.unit || "Unit not identified"}</span></th>
                <td>{m.current.value_text}</td><td>{m.previous_quarter?.value_text ?? "—"}</td><td>{m.year_ago_quarter?.value_text ?? "—"}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </details>
      {q.omitted && q.omitted.length > 0 && (
        <p className="fine">Omitted: {q.omitted.map((o) => `${o.metric} (${o.reason})`).join("; ")}.</p>
      )}
      {q.warnings && q.warnings.length > 0 && <details className="research-disclosure"><summary>Verification notes ({q.warnings.length})</summary><ul className="gaps">{q.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></details>}
      <div className="ev-row">
        {[...new Set(q.metrics!.map((m) => m.evidence_id).filter((id): id is string => !!id))].map((id) => <EvidenceButton key={id} id={id} onOpen={onEvidence} />)}
        {q.source && <a className="btn btn-small btn-ghost" href={api.fileUrl(q.source.version_id, q.source.page_index)} target="_blank" rel="noopener">Open filing PDF</a>}
      </div>
      <p className="fine">{q.served === "cached" ? "Saved extraction" : "Extracted from the filing"} · Figures checked against the source; changes calculated from the stated values.</p>
    </Section>
  );
}
