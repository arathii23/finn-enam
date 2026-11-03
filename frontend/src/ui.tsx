import type { ReactNode } from "react";
import type { EvidenceIndexEntry } from "./api";
import { DOC_LABEL } from "./format";

export function StateBox({ kind, title, children, action }: { kind: "loading" | "partial" | "error" | "empty"; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={`state state-${kind}`} role={kind === "error" ? "alert" : "status"} aria-live="polite">
      <div className="state-title">
        {kind === "loading" && <span className="spinner" aria-hidden="true" />}
        <span className="state-tag">{{ loading: "Loading", partial: "Partial", error: "Failed", empty: "Empty" }[kind]}</span>
        {title}
      </div>
      {children && <div className="state-body">{children}</div>}
      {action}
    </div>
  );
}

export function Chip({ tone, children }: { tone?: "neutral" | "warn" | "ok" | "muted"; children: ReactNode }) {
  return <span className={`chip chip-${tone ?? "neutral"}`}>{children}</span>;
}

export function EvidenceButton({ id, entry, label: customLabel, onOpen }: { id: string; entry?: EvidenceIndexEntry; label?: string; onOpen: (id: string, el: HTMLElement) => void }) {
  const label = customLabel ?? (entry ? `${(DOC_LABEL[entry.doc_type] ?? entry.doc_type).replace("Earnings-call transcript", "Transcript")} ${entry.period_label ?? ""} · PDF p.${entry.page_index}` : "Evidence");
  return (
    <button type="button" className="ev-btn" onClick={(e) => onOpen(id, e.currentTarget)} aria-label={`Inspect evidence: ${label}`}>
      <span aria-hidden="true">❝</span> {label}
    </button>
  );
}

export function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      <div className="card-head"><h2>{title}</h2>{aside}</div>
      {children}
    </section>
  );
}
