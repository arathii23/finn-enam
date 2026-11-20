import { useEffect, useState } from "react";
import { api, IS_STATIC, type TrustReport } from "./api";
import { istDateTime } from "./format";
import { Section, StateBox } from "./ui";

const labels: Record<string, string> = {
  exact_quotes: "Verbatim extracts", citations: "Citation locators", attributions: "Management attribution",
  absent_questions: "Unsupported questions", answerable_questions: "Source brief coverage",
  partly_overlapping_questions: "Partly overlapping questions",
  injection_fixture: "Source instruction fixture", xbrl_oracles: "XBRL reference values",
};

export function TrustView() {
  const [report, setReport] = useState<TrustReport | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.trust().then(setReport).catch((e: Error) => setError(e.message)); }, []);
  if (error) return <StateBox kind="error" title="Coverage could not load">{error}</StateBox>;
  if (!report) return <StateBox kind="loading" title="Loading coverage…" />;
  const evaluation = report.evaluation;
  return <div className="stack">
    <section className="card">
      <h1>Source coverage and quality</h1>
      <p className="muted">See which sources FINN has for each holding and how its source briefs performed in the latest local evaluation.</p>
    </section>
    <Section title={`Coverage · ${report.holdings.length} holdings`}>
      <p className="fine">Latest verified documents in this copy of FINN. Results refer to exchange XBRL. A filings check records an attempt and its outcome.</p>
      <ul className="trust-holdings">{report.holdings.map((row) => <li key={row.symbol}>
        <a className="btn btn-small btn-ghost" href={`#/c/${encodeURIComponent(row.symbol)}${IS_STATIC ? "" : "?mode=live"}`}>{row.symbol}</a>
        <dl>
          <div><dt>Annual report</dt><dd>{row.annual_period ?? "Unavailable"}</dd></div>
          <div><dt>Transcript</dt><dd>{row.transcript_date ?? "Unavailable"}{row.verified_roster !== null && <span className="sub">{row.verified_roster ? "Speaker roster verified" : "Speaker roster unverified"}</span>}</dd></div>
          <div><dt>XBRL quarter</dt><dd>{row.results_quarter ?? "Unavailable"}</dd></div>
          <div><dt>Last filings check</dt><dd>{row.last_filings_check ? istDateTime(row.last_filings_check) : "No check recorded"}{row.last_filings_check && <span className="sub">{row.filings_check_state === "fetched" ? "Response received" : row.filings_check_state.replace(/_/g, " ")}</span>}</dd></div>
        </dl>
      </li>)}</ul>
    </Section>
    <Section title="Latest local evaluation">
      {evaluation ? <>
        <p className="fine">{istDateTime(evaluation.generated_at)} · {evaluation.scope}</p>
        <dl className="trust-eval">{Object.entries(evaluation.checks).map(([key, check]) => <div key={key}>
          <dt>{labels[key] ?? key}</dt><dd>{check.total > 0 && `${check.passed}/${check.total} passed`}{check.total > 0 && !!check.not_run && " · "}{!!check.not_run && `${check.not_run} not run`}{!check.total && !check.not_run && "No samples"}</dd>
        </div>)}</dl>
        <p>Local keyless latency p50 {evaluation.latency_ms.p50 ?? "—"} ms · p95 {evaluation.latency_ms.p95 ?? "—"} ms over {evaluation.latency_ms.samples} requests. Model cost ${evaluation.model_cost_usd}.</p>
      </> : <p>No dated evaluation is available in this build.</p>}
    </Section>
    <Section title="What FINN will not do">
      <ul><li>Give buy or sell advice.</li><li>Fill a missing figure or answer from model memory.</li><li>Attribute a price move to a filing.</li><li>Include a source published after the replay cutoff in a replay answer.</li></ul>
    </Section>
  </div>;
}
