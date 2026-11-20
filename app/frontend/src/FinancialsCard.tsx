import { useEffect, useState } from "react";
import { api, ApiError, IS_STATIC, type Financials, type FinancialMetric, type FinancialSource, type Quarterly, type QMetric, type FinancialBasis, type ResearchMode } from "./api";
import { istDateTime } from "./format";
import { Chip, Section, StateBox } from "./ui";

type Props = { symbol: string; mode: ResearchMode; onAvailability?: (value: boolean) => void };

const crores = (value: string | null | undefined) => {
  if (value == null) return "Not available";
  const number = Number(value);
  return Number.isFinite(number) ? `₹${number.toLocaleString("en-IN", { maximumFractionDigits: 1 })} crore` : "Not available";
};

const pct = (value: number | null | undefined) => value == null ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;

function SourceDetails({ source, title }: { source: FinancialSource | null | undefined; title: string }) {
  if (!source) return <p className="fine">No source record is available for this value.</p>;
  return <details className="research-disclosure financial-source">
    <summary>{title}</summary>
    <p className="fine">{source.basis} · quarter ended {source.period_end} · exchange publication {istDateTime(source.published_at)} · {source.revision.toLowerCase() === "revision" ? `Revised on ${istDateTime(source.published_at)}` : source.revision}</p>
    <p className="fine">XBRL SHA-256: <code>{source.xbrl_hash}</code></p>
    <ul className="coverage">
      {source.concepts.map((fact, index) => <li key={`${fact.concept}-${index}`}>
        <span>{fact.role}: <code>{fact.concept}</code><span className="sub">{[fact.period_start, fact.period_end].filter(Boolean).join(" to ")}</span></span><span><code>{fact.raw_value}</code> {fact.unit}</span>
      </li>)}
    </ul>
    <div className="financial-links">
      <a className="btn btn-small btn-ghost" href={source.xbrl_url} target="_blank" rel="noopener noreferrer">Open XBRL</a>
      {source.pdf_url && <a className="btn btn-small btn-ghost" href={source.pdf_url} target="_blank" rel="noopener noreferrer">Open results PDF</a>}
    </div>
    {!source.pdf_url && <p className="fine">NSE did not include a PDF with this structured record.</p>}
  </details>;
}

function Trend({ values }: { values: (number | null)[] }) {
  const known = values.filter((value): value is number => value !== null && Number.isFinite(value));
  if (known.length < 2) return null;
  const low = Math.min(...known), span = Math.max(...known) - low || 1;
  const points = values.map((value, i) => value === null ? null :
    { x: 3 + i * 94 / (values.length - 1), y: 23 - (value - low) * 20 / span });
  return <svg className="financial-trend" width="100" height="26" viewBox="0 0 100 26" aria-hidden="true">
    {points.map((point, index) => {
      const previous = points[index - 1];
      return point && previous ? <line key={index} x1={previous.x} y1={previous.y} x2={point.x} y2={point.y} /> : null;
    })}
    {points.map((point, index) => point && <circle key={index} cx={point.x} cy={point.y} r="2" />)}
  </svg>;
}

function MetricCard({ metric, pdf }: { metric: FinancialMetric; pdf?: QMetric }) {
  const page = pdf?.source?.page_index;
  const url = pdf?.source?.url;
  const pdfLink = page && url && url.startsWith("https://") ? `${url.split("#")[0]}#page=${page}` : null;
  const gap = pdf && Math.abs(pdf.current.value - Number(metric.current.value_crore));
  const currencyKnown = /₹|\bINR\b/i.test(pdf?.unit ?? "");
  return <li className="financial-metric">
    <div className="financial-metric-head"><strong>{metric.label}</strong><strong>{crores(metric.current.value_crore)}</strong></div>
    <div className="financial-metric-changes">
      <span>QoQ {pct(metric.qoq_pct)}</span><span>YoY {pct(metric.yoy_pct)}</span>
    </div>
    {metric.source.revision.toLowerCase() === "revision" && <p className="fine">Revised on {istDateTime(metric.source.published_at)}.
      {metric.previous && <> Prior filing: {crores(metric.previous.value.value_crore)} on {istDateTime(metric.previous.published_at)}. <a href={metric.previous.url}>Earlier XBRL</a></>}</p>}
    {pdf && <details className="research-disclosure financial-discrepancy">
      <summary>Differs from PDF</summary>
      <p className="fine">PDF {pdf.current.value_text} {pdf.unit} · XBRL ₹{metric.current.value_crore} crore.</p>
      <p className="fine">Numeric gap {gap?.toFixed(2)} in the displayed crore figures{currencyKnown && pdf.current.value !== 0 ? ` (${(gap! / Math.abs(pdf.current.value) * 100).toFixed(2)}% of the PDF value)` : ""}.
        {!currencyKnown && " PDF currency is unidentified."} Verify the source definitions before comparing.</p>
      <div className="financial-links">
        {pdfLink ? <a className="btn btn-small" href={pdfLink} target="_blank" rel="noopener noreferrer">Open PDF · p.{page}</a> : <span className="fine">PDF page link unavailable</span>}
        <a className="btn btn-small" href={metric.source.xbrl_url} target="_blank" rel="noopener noreferrer">Open XBRL</a>
      </div>
      <p className="fine">XBRL tag: {metric.source.concepts.map((fact) => fact.concept).join(", ")}</p>
    </details>}
    <details className="research-disclosure">
      <summary>Reported values and calculation</summary>
      {metric.formula && <p className="fine"><strong>Formula:</strong> {metric.formula}</p>}
      <p className="fine"><strong>Exact current value:</strong> <code>{metric.current.value_raw}</code> {metric.current.unit}</p>
      {metric.derivation.length > 0 && <ul className="coverage">
        {metric.derivation.map((item) => <li key={item.role}><span>{item.role} · <code>{item.concept}</code></span><span><code>{item.value_raw}</code> {item.unit}</span></li>)}
      </ul>}
      <SourceDetails source={metric.source} title="Current-quarter exchange record" />
      <div className="financial-comparatives">
        <SourceDetails source={metric.comparative_sources.previous_quarter} title={`QoQ comparison · ${metric.qoq_period_end ?? "period unavailable"}`} />
        <SourceDetails source={metric.comparative_sources.year_ago_quarter} title={`YoY comparison · ${metric.yoy_period_end ?? "period unavailable"}`} />
      </div>
    </details>
  </li>;
}

export function FinancialsCard({ symbol, mode, onAvailability }: Props) {
  const [requestedBasis, setBasis] = useState<FinancialBasis | "auto">("auto");
  const [data, setData] = useState<Financials | null>(null);
  const [pdf, setPdf] = useState<Quarterly | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null); setData(null);
    api.financials(symbol, mode, requestedBasis)
      .then((value) => { if (active) { setData(value); onAvailability?.(value.available); } })
      .catch((error: ApiError) => { if (active) { setError(error); onAvailability?.(false); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [symbol, mode, requestedBasis, attempt, onAvailability]);
  useEffect(() => {
    let active = true;
    setPdf(null);
    api.quarterly(symbol, mode).then((result) => { if (active) setPdf(result); }).catch(() => {});
    return () => { active = false; };
  }, [symbol, mode]);

  const refresh = async () => {
    setRefreshing(true); setRefreshMessage(null);
    try {
      const result = await api.refreshFinancials(symbol);
      const companies = result.companies as { state?: string; stored?: number; issue?: string }[] | undefined;
      const company = companies?.[0];
      setRefreshMessage(company?.issue ?? `${company?.stored ?? 0} verified XBRL filing versions stored. No model call was made.`);
      setAttempt((n) => n + 1);
    } catch (e) {
      setRefreshMessage(e instanceof Error ? e.message : "The exchange results check could not complete.");
    } finally { setRefreshing(false); }
  };

  if (loading) return <Section title="Results scorecard"><p className="muted">Loading stored exchange results…</p></Section>;
  if (error) return <Section title="Results scorecard"><StateBox kind="partial" title="Exchange results could not be loaded">{error.message}</StateBox></Section>;
  if (!data) return null;
  const score = data.scorecard;
  const basis = data.basis;
  const trajectory = [...data.cards.trajectory.items].reverse();
  const differentPdfValues = pdf?.available && pdf.basis === basis && pdf.columns?.current_end === score.period_end
    ? score.metrics.flatMap((metric) => {
      const original = pdf.metrics?.find((row) => row.key === metric.key);
      const structured = metric.current.value_crore;
      return original && structured !== null && original.unit?.toLowerCase().includes("crore")
        && Math.abs(original.current.value - Number(structured)) >= 0.01 ? [{ metric, original }] : [];
    }) : [];
  return <Section title="Results scorecard" aside={<Chip tone="muted">{basis}</Chip>}>
    <div className="financial-controls" role="group" aria-label="Reporting basis">
      {(["consolidated", "standalone"] as const).map((choice) => {
        const period = data.periods_by_basis?.[choice];
        const label = period ? new Intl.DateTimeFormat("en-IN", { month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(period)) : "no filing";
        return <button key={choice} className={`btn btn-small${basis === choice ? " selected" : ""}`} aria-pressed={basis === choice}
          onClick={() => setBasis(choice)}>{choice === "consolidated" ? "Consolidated" : "Standalone"} · {label}</button>;
      })}
    </div>
    {data.other_basis?.period_end && (!score.period_end || data.other_basis.period_end > score.period_end) && <p className="fine">A newer {data.other_basis.name} filing is available for {data.other_basis.period_end}.</p>}
    {score.period_end && basis === "standalone" && (!data.periods_by_basis?.consolidated || data.periods_by_basis.consolidated < score.period_end)
      && <p className="fine">No verified consolidated filing for the quarter ended {score.period_end} in this copy.</p>}
    {score.available ? <>
      <p className="fine">Quarter ended {score.period_end} · {basis} · exchange structured filing. Values are shown in rupees crore; open a value to inspect the raw tag, publication time, file hash and source files.</p>
      <ul className="financial-metrics">{score.metrics.map((metric) => <MetricCard key={metric.key} metric={metric}
        pdf={differentPdfValues.find((item) => item.metric.key === metric.key)?.original} />)}</ul>
      {score.metrics.some((metric) => metric.key === "ebitda") && <p className="fine">EBITDA is derived from tagged items using the formula shown. A company’s own EBITDA definition may differ.</p>}
    </> : <StateBox kind="partial" title="No verified quarter is available for this view">
      <ul>{score.gaps.map((gap) => <li key={gap}>{gap}</li>)}</ul>
      {mode === "replay" && <p className="fine">The 30 April 2025 replay cutoff is preserved. The existing PDF based quarterly card remains below.</p>}
    </StateBox>}
    {mode === "live" && !IS_STATIC && <button className="btn btn-small" disabled={refreshing} onClick={refresh}>
      {refreshing ? "Checking NSE results…" : "Check latest exchange results"}
    </button>}
    {refreshMessage && <p className="fine" role="status">{refreshMessage}</p>}
    <details className="research-disclosure financial-pull-cards">
      <summary>Financial snapshot</summary>
      <div className="financial-mini-grid">{data.cards.financial_snapshot.items.map((item) => <div key={item.key} className="financial-mini-card">
        <span className="fine">{item.label}</span><strong>{item.value?.value_crore != null ? crores(item.value.value_crore) : item.value?.value != null ? `${item.value.value} ${item.value.unit ?? ""}` : "Not tagged"}</strong>
        {item.formula && <span className="fine">{item.formula}</span>}
        {item.growth && <span className="fine">QoQ {pct(item.growth.qoq_pct)} · YoY {pct(item.growth.yoy_pct)}</span>}
        <SourceDetails source={item.source} title="Exchange source" />
      </div>)}</div>
      {data.cards.financial_snapshot.gaps.map((gap) => <p className="fine" key={gap}>{gap}</p>)}
    </details>
    <details className="research-disclosure financial-pull-cards">
      <summary>Balance sheet{data.cards.balance_sheet.as_of ? ` · ${data.cards.balance_sheet.as_of}` : ""}</summary>
      <p className="fine">Period-end balances compared with {data.cards.balance_sheet.comparison_period ?? "the prior 31 March when tagged"}.</p>
      <ul className="coverage financial-balance-list">{data.cards.balance_sheet.items.map((item) => <li key={item.key} className="financial-balance-row">
        <div><span>{item.label}</span><span>{item.current ? crores(item.current.value_crore) : item.value ? `${item.value} ${item.unit}` : "Not tagged"}{item.previous_march && ` · March ${crores(item.previous_march.value_crore)}`}</span></div>
        {item.formula && <p className="fine">Formula: {item.formula}</p>}
        <SourceDetails source={item.source} title="Current-period source" />
        {item.previous_march_source && <SourceDetails source={item.previous_march_source} title="Previous 31 March source" />}
      </li>)}</ul>
      {data.cards.balance_sheet.gaps.map((gap) => <p className="fine" key={gap}>{gap}</p>)}
    </details>
    <details className="research-disclosure financial-pull-cards">
      <summary>Cash quality</summary>
      <p className="fine">{data.cards.cash_quality.period_type ?? "Period not identified"} · quarter ended {data.cards.cash_quality.period_end ?? "not available"}</p>
      <ul className="coverage">
        <li><span>Operating cash flow</span><span>{crores(data.cards.cash_quality.operating_cash_flow?.value_crore)}</span></li>
        <li><span>PAT</span><span>{crores(data.cards.cash_quality.pat?.value_crore)}</span></li>
        <li><span>Cash conversion</span><span>{pct(data.cards.cash_quality.cash_conversion_pct)}</span></li>
        <li><span>Tagged capex</span><span>{crores(data.cards.cash_quality.capex?.value_crore)}</span></li>
        <li><span>Free cash flow</span><span>{crores(data.cards.cash_quality.free_cash_flow?.value_crore)}</span></li>
      </ul>
      <p className="fine">Free cash flow here means operating cash flow less tagged capex; it may differ from a company’s reported definition.</p>
      <SourceDetails source={data.cards.cash_quality.sources?.operating_cash_flow} title="Operating cash flow source" />
      <SourceDetails source={data.cards.cash_quality.sources?.pat} title="PAT source" />
      <SourceDetails source={data.cards.cash_quality.sources?.capex} title="Capex source" />
      {data.cards.cash_quality.gaps.map((gap) => <p className="fine" key={gap}>{gap}</p>)}
    </details>
    <details className="research-disclosure financial-pull-cards">
      <summary>Quarterly trajectory · {data.cards.trajectory.items.length} quarters</summary>
      {trajectory.length > 1 && <div className="financial-trends">
        <div><span>{score.bank_taxonomy ? "Net interest income" : "Revenue"}</span><Trend values={trajectory.map((row) => row.revenue?.value_crore == null ? null : Number(row.revenue.value_crore))} /></div>
        {!score.bank_taxonomy && <div><span>EBITDA margin</span><Trend values={trajectory.map((row) => row.ebitda_margin_pct)} /></div>}
        <div><span>PAT</span><Trend values={trajectory.map((row) => row.pat?.value_crore == null ? null : Number(row.pat.value_crore))} /></div>
      </div>}
      <div className="table-wrap"><table><thead><tr><th>Quarter</th><th>Revenue / NII</th><th>EBITDA margin (non-bank)</th><th>PAT</th><th>Evidence</th></tr></thead>
        <tbody>{data.cards.trajectory.items.map((row) => <tr key={row.period_end}>
          <td>{row.period_end}{row.annual && <details className="research-disclosure"><summary>March FY</summary><p className="fine">Annual revenue / NII: {crores(row.annual.revenue?.value_crore)} · PAT {crores(row.annual.pat?.value_crore)} · EBITDA margin {row.annual.ebitda_margin_pct == null ? "—" : `${row.annual.ebitda_margin_pct.toFixed(1)}%`}</p><SourceDetails source={row.annual.source} title="Annual source" /></details>}</td>
          <td>{crores(row.revenue?.value_crore)}</td><td>{row.ebitda_margin_pct == null ? "—" : `${row.ebitda_margin_pct.toFixed(1)}%`}</td><td>{crores(row.pat?.value_crore)}</td>
          <td><SourceDetails source={row.source} title="Quarter source" /></td>
        </tr>)}</tbody></table></div>
      {data.cards.trajectory.gaps.map((gap) => <p className="fine" key={gap}>{gap}</p>)}
    </details>
  </Section>;
}
