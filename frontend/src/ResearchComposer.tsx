import { useId, useState } from "react";
import { Section } from "./ui";
import "./research.css";

const PROMPTS = [
  { label: "Business model", question: "What does the company do, and what are its main business segments?" },
  { label: "Management guidance", question: "What has management explicitly guided, and for which period?" },
  { label: "Key assumptions", question: "What assumptions and conditions underpin management's outlook?" },
];

export function ResearchComposer({ onSubmit, busy = false, initialQuestion = "", title = "Ask a focused question" }: {
  onSubmit: (question: string) => void | Promise<void>;
  busy?: boolean;
  initialQuestion?: string;
  title?: string;
}) {
  const id = useId();
  const [question, setQuestion] = useState(initialQuestion);
  const [error, setError] = useState<string | null>(null);
  const trimmed = question.trim();
  return (
    <Section title={title}>
      <p className="fine">Research the business and management commentary from primary documents available by the replay cutoff.</p>
      <details className="research-disclosure">
      <summary>Write or choose a question</summary>
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
        try { await onSubmit(trimmed); }
        catch (e) { setError(e instanceof Error ? e.message : "Research could not start."); }
      }}>
        <label htmlFor={id}>Your question</label>
        <textarea id={id} value={question} maxLength={300} rows={3} disabled={busy}
          onChange={(event) => setQuestion(event.target.value)}
          aria-describedby={`${id}-help`} placeholder="What would you like to understand?" />
        <div className="composer-bottom">
          <span id={`${id}-help`} className="fine">{question.length}/300 characters</span>
          <button className="btn btn-primary" type="submit" disabled={busy || !trimmed || question.length > 300}>
            {busy ? "Starting research…" : "Research question"}
          </button>
        </div>
        <p className="fine">Runs only when you select Research question. Missing evidence is shown as a gap.</p>
        {error && <p className="composer-error" role="alert">{error}</p>}
      </form>
      </details>
    </Section>
  );
}
