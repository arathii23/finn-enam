import { useEffect, useId, useState } from "react";
import { IS_STATIC, type ResearchMode } from "./api";
import { liveAppUrl } from "./links";
import { SaveToNotebook } from "./Notebook";
import { Section } from "./ui";
import "./research.css";

const PROMPTS = [
  { label: "Business model", question: "What does the company do, and what are its main business segments?" },
  { label: "Management guidance", question: "What has management explicitly guided, and for which period?" },
  { label: "Key assumptions", question: "What assumptions and conditions underpin management's outlook?" },
];

export function ResearchComposer({ onSubmit, busy = false, initialQuestion = "", title = "Ask a focused question", symbol, company, mode = "replay", cutoff, eventId }: {
  onSubmit: (question: string) => void | Promise<void>;
  busy?: boolean;
  initialQuestion?: string;
  title?: string;
  symbol?: string; company?: string; mode?: ResearchMode; cutoff?: string | null; eventId?: string | null;
}) {
  const id = useId();
  const storageKey = symbol ? `finn.question.draft.${symbol}.${mode}` : null;
  const [question, setQuestion] = useState(() => {
    if (initialQuestion) return initialQuestion;
    try { return storageKey ? sessionStorage.getItem(storageKey) || "" : ""; } catch { return ""; }
  });
  const [error, setError] = useState<string | null>(null);
  const trimmed = question.trim();
  useEffect(() => { if (storageKey) { try { sessionStorage.setItem(storageKey, question); } catch { /* Draft persistence is optional. */ } } }, [storageKey, question]);
  return (
    <Section title={title}>
      <p className="fine">{mode === "replay" ? "Ask about primary documents available by the replay cutoff." : "A research request checks for current primary sources and shows their actual dates and coverage."}</p>
      <div className="research-prompts" aria-label="Question suggestions">
        {PROMPTS.map((prompt) => (
          <button key={prompt.label} type="button" className="btn btn-small" disabled={busy}
            onClick={() => { setQuestion(prompt.question); setError(null); }}>{prompt.label}</button>
        ))}
      </div>
      <form className="research-composer" onSubmit={async (event) => {
        event.preventDefault();
        if (!trimmed || question.length > 300 || busy) return;
        setError(null);
        if (IS_STATIC) return;
        try { await onSubmit(trimmed); }
        catch (e) { setError(e instanceof Error ? e.message : "Research could not start."); }
      }}>
        <label htmlFor={id}>Your question</label>
        <textarea id={id} value={question} maxLength={300} rows={3} disabled={busy}
          onChange={(event) => setQuestion(event.target.value)}
          aria-describedby={`${id}-help`} placeholder="What would you like to understand?" />
        <div className="composer-bottom">
          <span id={`${id}-help`} className="fine">{question.length}/300 characters</span>
          {IS_STATIC ? <a className={`btn btn-primary${!trimmed ? " is-disabled" : ""}`} aria-disabled={!trimmed} href={trimmed ? liveAppUrl({ symbol, question: trimmed, eventId, mode }) : undefined}>Ask in live app ↗</a> : <button className="btn btn-primary" type="submit" disabled={busy || !trimmed || question.length > 300}>
            {busy ? "Starting research…" : "Research question"}
          </button>}
        </div>
        <p className="fine">{IS_STATIC ? "Opens the live app with your question filled in. Select Research there to run it; the free service may take a minute to wake." : "Runs only when you select Research question. Missing evidence is shown as a gap."}</p>
        {symbol && trimmed && <SaveToNotebook label="Keep as follow-up" draft={{ symbol, company: company || symbol, kind: "follow_up", text: trimmed, question: trimmed, mode, cutoff }} />}
        {error && <p className="composer-error" role="alert">{error}</p>}
      </form>
    </Section>
  );
}
