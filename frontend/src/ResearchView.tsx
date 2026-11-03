import { useEffect, useRef, useState } from "react";
import { api, ApiError, type BriefItem, type Job, type ResearchOutput, type Section as Sec } from "./api";
import { docLabel, istDateTime } from "./format";
import { Chip, EvidenceButton, Section, StateBox } from "./ui";

const STAGE_LABEL: Record<string, string> = {
  resolving_company: "Resolving company",
  discovering_sources: "Finding source records",
  downloading_sources: "Downloading and reading primary documents",
  finding_documents: "Finding eligible documents",
  reading_sources: "Reading sources",
  preparing_research: "Preparing research",
};

type Props = { jobId: string; onEvidence: (id: string, el: HTMLElement) => void; onBack: () => void; onRetry: (symbol: string, eventId?: string | null, question?: string | null) => void | Promise<void> };

export function ResearchView({ jobId, onEvidence, onBack, onRetry }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [now, setNow] = useState(Date.now());
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    let live = true;
    const poll = async () => {
      try {
        const j = await api.job(jobId);
        if (!live) return;
        setJob(j); setError(null);
        if (["queued", "running"].includes(j.state)) timer.current = window.setTimeout(poll, 2000);
      } catch (e) {
        if (live) { setError(e as ApiError); timer.current = window.setTimeout(poll, 4000); }
      }
    };
    poll();
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    return () => { live = false; window.clearTimeout(timer.current); window.clearInterval(tick); };
  }, [jobId]);

  if (!job) {
    return error ? <StateBox kind="error" title="Research job could not be loaded">{error.message} Retrying…</StateBox>
      : <StateBox kind="loading" title="Loading research job…" />;
  }
  const running = ["queued", "running"].includes(job.state);
  const elapsed = Math.round(((running ? now : Date.parse(job.updated_at)) - Date.parse(job.created_at)) / 1000);
  const done = new Set(job.stages.filter((s) => s.finished_at).map((s) => s.stage));
  const r = job.result;
  const retryJob = async () => {
    setRetrying(true); setRetryError(null);
    try { await onRetry(job.request.symbol, job.request.event_id, job.request.question); }
    catch (e) { setRetryError(e instanceof Error ? e.message : "Research could not be restarted."); }
    finally { setRetrying(false); }
  };
  const researchQuestion = async (question: string) => {
    setRetrying(true); setRetryError(null);
    try { await onRetry(job.request.symbol, job.request.event_id, question); }
    catch (e) { setRetryError(e instanceof Error ? e.message : "Research could not be started."); }
    finally { setRetrying(false); }
  };

  return (
    <div className="stack">
      <button className="btn btn-ghost back" onClick={onBack}>← {job.request.symbol}</button>
      {retryError && <StateBox kind="error" title="Research could not restart">{retryError}</StateBox>}
      {error && <StateBox kind="error" title="Research status could not be refreshed">{error.message} Retrying automatically; the last received state remains below.</StateBox>}
      {(running || !r) && (
        <section className="card" aria-live="polite">
          <div className="card-head"><h2>{running ? "Research in progress" : "Research did not complete"}</h2><Chip tone="muted">{elapsed}s</Chip></div>
          <ol className="stages">
            {job.all_stages.map((s) => (
              <li key={s} className={done.has(s) ? "done" : job.stage === s ? "active" : ""}>
                <span aria-hidden="true">{done.has(s) ? "✓" : job.stage === s ? "●" : "○"}</span> {STAGE_LABEL[s] ?? s}
                {done.has(s) && <span className="sr-only"> (completed)</span>}
              </li>
            ))}
          </ol>
          {job.state === "failed" && <StateBox kind="error" title="The research job failed" action={<button className="btn" disabled={retrying} onClick={retryJob}>Retry</button>}>{job.error}</StateBox>}
          {job.state === "interrupted" && <StateBox kind="partial" title="Research needs a refresh" action={<button className="btn" disabled={retrying} onClick={retryJob}>Run again</button>}>{job.error}</StateBox>}
        </section>
      )}
      {r && <Result r={r} state={job.state} elapsed={elapsed} onEvidence={onEvidence} onRetry={retryJob} onQuestion={researchQuestion} retrying={retrying} />}
    </div>
  );
}

function Result({ r, state, elapsed, onEvidence, onRetry, onQuestion, retrying }: { r: ResearchOutput; state: string; elapsed: number; onEvidence: Props["onEvidence"]; onRetry: () => void; onQuestion: (question: string) => void; retrying: boolean }) {
  const unavailable = r.generation.status !== "generated";
  const budgetBlocked = r.generation.status === "budget_exhausted";
  const brief = r.source_brief && r.source_brief.status === "extractive" ? r.source_brief : null;
  const byKind = (k: string): BriefItem[] => (brief ? brief.highlights.filter((h) => h.kind === k) : []);
  return (
    <>
      <section className="card identity">
        <div className="eyebrow">{r.mode === "replay" ? `Historical replay · as of ${istDateTime(r.cutoff)}` : "Live"}</div>
        <div className="card-head"><h1>{r.company.legal_name}</h1><Chip tone={brief ? "neutral" : "muted"}>{brief ? "Source brief" : unavailable ? "Source passages" : "Saved result"}</Chip></div>
        {r.question && <div className="research-question"><span className="sub">Research question</span>{r.question}</div>}
        {r.event && <p className="event-ctx"><strong>{r.event.category}</strong> · {istDateTime(r.event.published_at)}</p>}
        <p className="fine">Prepared {istDateTime(r.generated_at)} · {r.eligible_version_ids.length} eligible documents · original run {elapsed}s.</p>
      </section>
      {state === "partial" && (
        <StateBox kind="partial" title={budgetBlocked ? "Research paused at the app spending limit" : brief ? "Keyless source brief" : unavailable ? "Research prose not generated" : "Some sections lack verified evidence"}
          action={<button className="btn" disabled={retrying} onClick={onRetry}>{retrying ? "Starting research…" : "Retry research"}</button>}>
          {budgetBlocked ? "This research attempt reached FINN's spending limit. You can still inspect its source passages below. Retrying requires available allowance within the configured limit."
            : brief ? "No model is configured, so this is a verbatim extractive brief: the sentences most relevant to your question are quoted exactly from the primary sources and cited. Figures are quoted, never computed."
            : unavailable ? "A new summary could not be generated. Your verified primary-source passages remain available below, without added commentary."
            : "Statements without verified citations were removed; see evidence gaps."}
        </StateBox>
      )}
      {brief && brief.suggested_questions.length > 0 && (
        <section className="card">
          <p className="fine" style={{ marginTop: 0 }}>Ask a focused question — it re-runs retrieval against the same primary sources:</p>
          <div className="chip-row">
            {brief.suggested_questions.map((q) => (
              <button key={q} type="button" className="chip-btn" disabled={retrying} onClick={() => onQuestion(q)}>{q}</button>
            ))}
          </div>
        </section>
      )}
      {r.event_filing && <ResearchSection title="What the filing states" s={r.event_filing} r={r} highlights={byKind("event_filing")} onEvidence={onEvidence} />}
      <ResearchSection title="Business context" s={r.business_context} r={r} highlights={byKind("business_context")} onEvidence={onEvidence} />
      <ResearchSection title="Management commentary" s={r.management_commentary} r={r} highlights={byKind("management_commentary")} onEvidence={onEvidence} />
      <Section title="Evidence gaps">
        <ul className="gaps">
          {r.evidence_gaps.map((g, i) => (
            <li key={i}><Chip tone={g.kind === "coverage" ? "muted" : g.kind === "model" ? "warn" : "neutral"}>{g.kind === "model" ? "Summary" : g.kind}</Chip> {g.kind === "model" && unavailable ? "A new summary is unavailable; the retrieved source passages are shown directly." : g.text}
              {g.evidence_ids.map((id) => <EvidenceButton key={id} id={id} entry={r.evidence_index[id]} onOpen={onEvidence} />)}</li>
          ))}
        </ul>
      </Section>
      <Section title="Follow-up question">
        {r.follow_up.status === "generated" && r.follow_up.text ? (
          <>
            <p className="followup">{r.follow_up.text}</p>
            <div className="ev-row">{r.follow_up.evidence_ids.map((id) => <EvidenceButton key={id} id={id} entry={r.evidence_index[id]} onOpen={onEvidence} />)}</div>
            {r.follow_up.text.length <= 300 ? <button className="btn btn-small" disabled={retrying} onClick={() => onQuestion(r.follow_up.text!)}>{retrying ? "Starting research…" : "Research this question"}</button>
              : <p className="fine">Open the company to refine this question to 300 characters before researching it.</p>}
            <p className="fine">Starts a separate research request using the same company and event context.</p>
          </>
        ) : <p className="muted">{budgetBlocked ? "A follow-up was not generated because this attempt reached the app spending limit." : "A follow-up question was not generated. You can return to the company to ask a focused question."}</p>}
      </Section>
    </>
  );
}

function ResearchSection({ title, s, r, highlights, onEvidence }: { title: string; s: Sec; r: ResearchOutput; highlights: BriefItem[]; onEvidence: Props["onEvidence"] }) {
  const hasBrief = s.claims.length === 0 && highlights.length > 0;
  const tone = s.status === "generated" ? "ok" : hasBrief ? "neutral" : s.status === "insufficient_evidence" ? "warn" : "muted";
  const label = s.status === "generated" ? "Cited" : hasBrief ? "Verbatim extracts" :
    ({ model_unavailable: "Passages only", insufficient_evidence: "Insufficient evidence", failed: "Generation failed" }[s.status] ?? s.status);
  return (
    <Section title={title} aside={<Chip tone={tone}>{label}</Chip>}>
      {s.claims.length > 0 && (
        <ul className="claims">
          {s.claims.map((c, i) => (
            <li key={i}>
              <p>{c.speaker && <strong>{c.speaker}: </strong>}{c.text}</p>
              <div className="ev-row">{c.evidence_ids.map((id) => <EvidenceButton key={id} id={id} entry={r.evidence_index[id]} onOpen={onEvidence} />)}</div>
            </li>
          ))}
        </ul>
      )}
      {hasBrief && (
        <ul className="brief-quotes">
          {highlights.map((h) => {
            const e = r.evidence_index[h.evidence_id];
            return (
              <li key={h.evidence_id}>
                <blockquote className="brief-quote">
                  {h.speaker && <strong>{h.speaker}: </strong>}“{h.quote}”
                </blockquote>
                <div className="ev-row">
                  <span className="passage-meta">{docLabel(h.doc_type, h.period_label)} · PDF p.{h.page_index}</span>
                  <EvidenceButton id={h.evidence_id} entry={e} onOpen={onEvidence} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {s.claims.length === 0 && highlights.length === 0 && s.candidate_evidence_ids.length > 0 && (
        <>
          <p className="fine">Retrieved passages (unsummarised, ranked by keyword relevance):</p>
          <ul className="passages">
            {s.candidate_evidence_ids.map((id) => {
              const e = r.evidence_index[id];
              return (
                <li key={id}>
                  <button type="button" className="passage-btn" onClick={(ev) => onEvidence(id, ev.currentTarget)}>
                    <span className="passage-meta">{docLabel(e?.doc_type ?? "", e?.period_label)} · PDF p.{e?.page_index}{e?.speaker ? ` · ${e.speaker}` : ""}</span>
                    <span className="passage-text">{e?.excerpt}…</span>
                    <span className="passage-cta">Inspect evidence →</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
      {s.claims.length === 0 && highlights.length === 0 && s.candidate_evidence_ids.length === 0 && <p className="muted">{s.note ?? "No eligible passages."}</p>}
    </Section>
  );
}
