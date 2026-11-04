import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Narrative, type NarrativeItem, type NarrativeStatement, type ResearchMode } from "./api";
import { docLabel } from "./format";
import { Chip, EvidenceButton, Section, StateBox } from "./ui";

type Props = { symbol: string; mode?: ResearchMode; onEvidence: (id: string, el: HTMLElement) => void; onBack: () => void };

export function NarrativeView({ symbol, mode = "replay", onEvidence, onBack }: Props) {
  const [data, setData] = useState<Narrative | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const load = useCallback(() => {
    setData(null); setError(null);
    api.narrative(symbol, mode).then(setData).catch(setError);
  }, [symbol, mode]);
  useEffect(load, [load]);

  if (error) {
    const unknown = error.state === "unknown_symbol";
    return (
      <div className="stack">
        <button className="btn btn-ghost back" onClick={onBack}>← {symbol}</button>
        <StateBox kind={unknown ? "empty" : "error"} title={unknown ? `Identity could not be resolved for “${symbol}”` : "Could not load the comparison"}
          action={<button className="btn" onClick={load}>Retry</button>}>{error.message}</StateBox>
      </div>
    );
  }
  if (!data) return (
    <div className="stack"><button className="btn btn-ghost back" onClick={onBack}>← {symbol}</button>
      <StateBox kind="loading" title={`Lining up ${symbol}'s guidance against outcomes…`} /></div>
  );

  return (
    <div className="stack">
      <button className="btn btn-ghost back" onClick={onBack}>← {symbol}</button>
      <section className="card identity">
        <div className="eyebrow">Numbers vs Narrative</div>
        <h1>{data.legal_name}</h1>
        <p className="muted">What management <strong>guided</strong> versus what the company <strong>delivered</strong> — matched only
          within the same metric, fiscal year and currency basis. Every figure opens at its exact source page.</p>
        {data.cutoff_display && <p className="fine">Historical replay · evidence available by {data.cutoff_display}.</p>}
        <p className="fine">Available history: {new Set(data.sources.filter((s) => s.doc_type === "earnings_call_transcript").map((s) => s.period_label).filter(Boolean)).size} transcript periods. These are annual guidance/outcome checks, not a complete four-quarter promise history.</p>
      </section>

      {data.items.length === 0 && (
        <StateBox kind="empty" title="No comparable headline guidance in the primary sources">
          {data.empty_reason ?? "FINN shows a verdict only when the sources support one."}
        </StateBox>
      )}

      {data.items.map((it, i) => <CompareCard key={i} it={it} ev={data.evidence_index} onEvidence={onEvidence} />)}

      {data.sources.length > 0 && (
        <Section title="Sources compared" aside={<Chip tone="muted">{data.sources.length}</Chip>}>
          <ul className="coverage">
            {data.sources.map((s) => (
              <li key={s.version_id}><span>{docLabel(s.doc_type, s.period_label)}</span>
                <a className="ev-btn" href={api.fileUrl(s.version_id)} target="_blank" rel="noopener">Open PDF</a></li>
            ))}
          </ul>
          <p className="fine">{data.method}</p>
        </Section>
      )}
    </div>
  );
}

const VERDICT_LABEL: Record<string, string> = {
  below_range: "Below guided range", within_range: "Within guided range", above_range: "Above guided range",
  pending: "Outcome pending", not_comparable: "Not comparable",
};

function CompareCard({ it, ev, onEvidence }: { it: NarrativeItem; ev: Narrative["evidence_index"]; onEvidence: Props["onEvidence"] }) {
  const g = it.guidance, o = it.outcome;
  return (
    <section className="card nv-card">
      <div className="card-head">
        <h2>{it.metric} · <span className="nv-fy">{it.fiscal_year}</span></h2>
        <Chip tone="muted">{it.basis}</Chip>
      </div>

      {it.comparable && o ? (
        <>
          <Band low={g.low} high={g.high} value={o.low} kind={it.verdict.kind} />
          <p className="nv-verdict">{it.verdict.summary}</p>
        </>
      ) : it.verdict.kind === "pending" ? (
        <>
          <Band low={g.low} high={g.high} value={null} kind="pending" />
          <p className="nv-verdict nv-muted">{it.verdict.summary}</p>
        </>
      ) : (
        <StateBox kind="partial" title={VERDICT_LABEL[it.verdict.kind] ?? "Not comparable"}>
          {it.verdict.summary}{it.gate_reasons.map((r) => <span key={r}> {r}</span>)}
        </StateBox>
      )}

      <div className="nv-rows">
        <StatementRow label="Guided" s={g} ev={ev} onEvidence={onEvidence} />
        {o ? <StatementRow label="Delivered" s={o} ev={ev} onEvidence={onEvidence} />
          : <div className="nv-row"><span className="nv-rowlabel">Delivered</span>
              <span className="nv-rowbody muted">Not yet reported by the evidence cutoff.</span></div>}
      </div>

      {it.caveats.length > 0 && (
        <div className="nv-caveats">
          {it.caveats.map((c, i) => (
            <div key={i} className="nv-caveat">
              <span className="nv-caveat-tag">Comparability note</span>
              <p>{c.text}</p>
              <div className="ev-row">{c.evidence_ids.map((id) => <EvidenceButton key={id} id={id} entry={ev[id]} onOpen={onEvidence} />)}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function StatementRow({ label, s, ev, onEvidence }: { label: string; s: NarrativeStatement; ev: Narrative["evidence_index"]; onEvidence: Props["onEvidence"] }) {
  return (
    <div className="nv-row">
      <span className="nv-rowlabel">{label}</span>
      <div className="nv-rowbody">
        <span className="nv-value">{s.value_text}</span>
        <span className="nv-src">{s.speaker ? `${s.speaker}` : "Results filing"}{s.source_period ? ` · ${s.source_period}` : ""}</span>
        {s.entity && <span className="nv-src">Reporting entity: {s.entity}</span>}
        {s.reporting_currency && !["constant currency", "not applicable"].includes(s.reporting_currency) && <span className="nv-src">Reported-growth currency: {s.reporting_currency}</span>}
        <div className="ev-row"><EvidenceButton id={s.evidence_id} entry={ev[s.evidence_id]} onOpen={onEvidence} /></div>
      </div>
    </div>
  );
}

// A calm value track: the guided range as a shaded band, the delivered value as an ink
// marker. Position alone shows below / within / above — no red/green, no verdict colour.
function Band({ low, high, value, kind }: { low: number; high: number; value: number | null; kind: string }) {
  const pts = [low, high, ...(value != null ? [value] : [])];
  const dataMin = Math.min(...pts), dataMax = Math.max(...pts);
  const span = Math.max(dataMax - dataMin, 1);
  const pad = Math.max(span * 0.45, 1);
  const axisMin = dataMin - pad, axisMax = dataMax + pad;
  const pct = (x: number) => Math.min(98, Math.max(2, ((x - axisMin) / (axisMax - axisMin)) * 100));
  const bandL = pct(low), bandW = Math.max(pct(high) - pct(low), 2.5);
  const fmt = (x: number) => (Number.isInteger(x) ? `${x}` : `${x}`) + "%";
  return (
    <div className={`nv-band-wrap${kind === "pending" ? " nv-pending" : ""}`} aria-hidden="true">
      <div className="nv-track">
        <div className="nv-band" style={{ left: `${bandL}%`, width: `${bandW}%` }} />
        <span className="nv-band-lo" style={{ left: `${bandL}%` }}>{fmt(low)}</span>
        {high !== low && <span className="nv-band-hi" style={{ left: `${pct(high)}%` }}>{fmt(high)}</span>}
        {value != null && (
          <div className="nv-marker" style={{ left: `${pct(value)}%` }}>
            <span className="nv-marker-val">{fmt(value)}</span>
          </div>
        )}
        {value == null && <span className="nv-pending-tag" style={{ left: `${Math.min(pct(high) + 8, 90)}%` }}>awaiting result</span>}
      </div>
    </div>
  );
}
