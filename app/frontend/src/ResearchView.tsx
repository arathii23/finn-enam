import { useEffect, useRef, useState } from "react";
import { api, ApiError, IS_STATIC, type BriefItem, type Job, type ResearchMode, type ResearchOutput, type Section as Sec } from "./api";
import { docLabel, istDateTime } from "./format";
import { Chip, EvidenceButton, Section, StateBox } from "./ui";
import { liveAppUrl } from "./links";
import { SaveToNotebook, type NotebookDraft } from "./Notebook";
import { ResearchComposer } from "./ResearchComposer";

const STAGE_LABEL: Record<string, string> = {
  resolving_company: "Resolving company",
  discovering_sources: "Finding source records",
  downloading_sources: "Downloading and reading primary documents",
  finding_documents: "Finding eligible documents",
  reading_sources: "Reading sources",
  preparing_research: "Preparing research",
};

type Props = { jobId: string; onEvidence: (id: string, el: HTMLElement) => void; onBack: () => void; onRetry: (symbol: string, eventId?: string | null, question?: string | null, mode?: ResearchMode) => void | Promise<void> };

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
        if (live) { setError(e as ApiError); if (!(e instanceof ApiError && e.status === 404)) timer.current = window.setTimeout(poll, 4000); }
      }
    };
    poll();
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    return () => { live = false; window.clearTimeout(timer.current); window.clearInterval(tick); };
  }, [jobId]);

  if (!job) {
    return error ? <StateBox kind="error" title="Research job could not be loaded" action={<button className="btn" onClick={onBack}>Return to company</button>}>{error.message} {error.status !== 404 && "Retrying…"}</StateBox>
      : <StateBox kind="loading" title="Loading research job…" />;
  }
  const running = ["queued", "running"].includes(job.state);
  const elapsed = Math.round(((running ? now : Date.parse(job.updated_at)) - Date.parse(job.created_at)) / 1000);
  const done = new Set(job.stages.filter((s) => s.finished_at).map((s) => s.stage));
  const r = job.result;
  const retryJob = async () => {
    setRetrying(true); setRetryError(null);
    try { await onRetry(job.request.symbol, job.request.event_id, job.request.question, job.request.mode === "live" ? "live" : "replay"); }
    catch (e) { setRetryError(e instanceof Error ? e.message : "Research could not be restarted."); }
    finally { setRetrying(false); }
  };
  const researchQuestion = async (question: string) => {
    setRetrying(true); setRetryError(null);
    try { await onRetry(job.request.symbol, job.request.event_id, question, job.request.mode === "live" ? "live" : "replay"); }
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
          {job.state === "failed" && <StateBox kind="error" title="The research job failed" action={IS_STATIC ? <a className="btn" href={liveAppUrl({ symbol: job.request.symbol, question: job.request.question, eventId: job.request.event_id, mode: job.request.mode === "live" ? "live" : "replay" })}>Research in live app ↗</a> : <button className="btn" disabled={retrying} onClick={retryJob}>Retry</button>}>{job.error}</StateBox>}
          {job.state === "interrupted" && <StateBox kind="partial" title="Research needs a refresh" action={IS_STATIC ? <a className="btn" href={liveAppUrl({ symbol: job.request.symbol, question: job.request.question, eventId: job.request.event_id, mode: job.request.mode === "live" ? "live" : "replay" })}>Research in live app ↗</a> : <button className="btn" disabled={retrying} onClick={retryJob}>Run again</button>}>{job.error}</StateBox>}
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
  const sectionSpecs = [
    { kind: "event_filing", title: "What the filing states", section: r.event_filing },
    { kind: "business_context", title: "Business context", section: r.business_context },
    { kind: "management_commentary", title: "Management commentary", section: r.management_commentary },
  ];
  if (brief) {
    const order = [...new Set(brief.highlights.map((item) => item.kind))];
    sectionSpecs.sort((a, b) => (order.includes(a.kind) ? order.indexOf(a.kind) : 99) - (order.includes(b.kind) ? order.indexOf(b.kind) : 99));
  }
  const mode: ResearchMode = r.mode === "live" ? "live" : "replay";
  const newestPublication = Object.values(r.evidence_index).map((entry) => entry.published_at).filter((stamp): stamp is string => !!stamp && Number.isFinite(Date.parse(stamp))).sort((a, b) => Date.parse(b) - Date.parse(a))[0];
  const link = (question?: string | null) => liveAppUrl({ symbol: r.company.symbol, eventId: r.event?.announcement_id, question: question || r.question, mode });
  return (
    <>
      <section className="card identity">
        <div className="eyebrow">{r.mode === "replay" ? "Historical replay" : "Current-source run"} · evidence by {istDateTime(r.cutoff)}</div>
        <div className="card-head"><h1>{r.company.legal_name}</h1><Chip tone={brief ? "neutral" : "muted"}>{brief ? "Source brief" : unavailable ? "Source passages" : "Saved result"}</Chip></div>
        {r.question && <div className="research-question"><span className="sub">Research question</span>{r.question}</div>}
        {r.event && <p className="event-ctx"><strong>{r.event.category}</strong> · {istDateTime(r.event.published_at)}</p>}
        <p className="fine">Prepared {istDateTime(r.generated_at)} · {r.eligible_version_ids.length} eligible documents · original run {elapsed}s.</p>
        {mode === "live" && <p className="fine source-freshness">Newest cited publication: {newestPublication ? istDateTime(newestPublication) : "not established"}. Source check: {r.discovery?.finished_at ? istDateTime(r.discovery.finished_at) : "not recorded"}{r.discovery?.cached ? " (recent check reused)" : ""}. Publication and reporting dates describe the evidence; a new question does not make older documents current.</p>}
        {r.question && <SaveToNotebook label="Keep question as follow-up" draft={notebookDraft(r, r.question, "follow_up")} />}
      </section>
      {state === "partial" && (
        <StateBox kind="partial" title={budgetBlocked ? "Research paused at the app spending limit" : brief ? "Keyless source brief" : unavailable ? "Research prose not generated" : "Some sections lack verified evidence"}
          action={IS_STATIC ? <a className="btn" href={link()}>Ask in live app ↗</a> : brief ? undefined : <button className="btn" disabled={retrying} onClick={onRetry}>{retrying ? "Starting research…" : "Retry research"}</button>}>
          {budgetBlocked ? "This research attempt reached FINN's spending limit. You can still inspect its source passages below. Retrying requires available allowance within the configured limit."
            : brief ? "Relevant sentences are quoted directly from the primary sources with citations. Read their full context before drawing a conclusion; figures here are quoted, not calculated."
            : unavailable ? "A new summary could not be generated. Your verified primary-source passages remain available below, without added commentary."
            : "Statements without verified citations were removed; see evidence gaps."}
        </StateBox>
      )}
      {brief && brief.suggested_questions.length > 0 && (
        <section className="card">
          <p className="fine" style={{ marginTop: 0 }}>Ask a focused question — it re-runs retrieval against the same primary sources:</p>
          <div className="chip-row">
            {brief.suggested_questions.map((q) => (
              IS_STATIC ? <a key={q} className="chip-btn" href={link(q)}>{q} ↗</a> : <button key={q} type="button" className="chip-btn" disabled={retrying} onClick={() => onQuestion(q)}>{q}</button>
            ))}
          </div>
        </section>
      )}
      {sectionSpecs.map(({ kind, title, section }) => section && <ResearchSection key={kind} title={title} s={section} r={r} highlights={byKind(kind)} onEvidence={onEvidence} />)}
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
            {r.follow_up.text.length <= 300 ? IS_STATIC ? <a className="btn btn-small" href={link(r.follow_up.text)}>Research question in live app ↗</a> : <button className="btn btn-small" disabled={retrying} onClick={() => onQuestion(r.follow_up.text!)}>{retrying ? "Starting research…" : "Research this question"}</button>
              : <p className="fine">Open the company to refine this question to 300 characters before researching it.</p>}
            <SaveToNotebook label="Keep as follow-up" draft={notebookDraft(r, r.follow_up.text, "follow_up", r.follow_up.evidence_ids)} />
            <p className="fine">Starts a separate research request using the same company and event context.</p>
          </>
        ) : <p className="muted">{budgetBlocked ? "A follow-up was not generated because this attempt reached the app spending limit." : "A follow-up question was not generated. You can return to the company to ask a focused question."}</p>}
      </Section>
      <ResearchComposer title="Continue this investigation" symbol={r.company.symbol} company={r.company.legal_name} mode={mode} cutoff={r.cutoff} eventId={r.event?.announcement_id} busy={retrying} onSubmit={onQuestion} />
    </>
  );
}

function notebookDraft(r: ResearchOutput, text: string, kind: NotebookDraft["kind"], ids: string[] = []): NotebookDraft {
  return { symbol: r.company.symbol, company: r.company.legal_name, text, kind, question: r.question, cutoff: r.cutoff, mode: r.mode,
    evidence: Object.fromEntries(ids.filter((id) => !!r.evidence_index[id]).map((id) => [id, r.evidence_index[id]])) };
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
              <div className="ev-row">{c.evidence_ids.map((id) => <EvidenceButton key={id} id={id} entry={r.evidence_index[id]} onOpen={onEvidence} />)}<SaveToNotebook draft={notebookDraft(r, c.text, "cited_point", c.evidence_ids)} /></div>
            </li>
          ))}
        </ul>
      )}
      {hasBrief && (
        <ul className="brief-quotes">
          {highlights.map((h) => {
            const e = r.evidence_index[h.evidence_id];
            const context = h.context_evidence_ids?.length ? highlights.filter((item) => h.context_evidence_ids!.includes(item.evidence_id)) : [h];
            const savedText = context.length > 1 ? context.map((item) => `PDF p.${item.page_index}:\n${item.quote}`).join("\n\n") : h.quote;
            return (
              <li key={h.evidence_id}>
                {context.length > 1 && <p className="fine">Read together with {context.filter((item) => item.evidence_id !== h.evidence_id).map((item) => `PDF p.${item.page_index}`).join(", ")}; the passage continues across source chunks.</p>}
                <blockquote className="brief-quote">
                  {h.speaker && <strong>{h.speaker}: </strong>}“{h.quote}”
                </blockquote>
                <div className="ev-row">
                  <span className="passage-meta">{docLabel(h.doc_type, h.period_label)} · PDF p.{h.page_index}{e?.published_at ? ` · published ${istDateTime(e.published_at)}` : ""}</span>
                  <EvidenceButton id={h.evidence_id} entry={e} onOpen={onEvidence} />
                  <SaveToNotebook label={context.length > 1 ? "Save quoted context" : "Save quote"} draft={notebookDraft(r, savedText, "source_quote", context.map((item) => item.evidence_id))} />
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
