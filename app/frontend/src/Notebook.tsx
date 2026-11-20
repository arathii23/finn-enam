import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type EvidenceIndexEntry } from "./api";
import { docLabel, istDateTime } from "./format";
import { Chip, Section } from "./ui";

type Source = { passage_id: string; version_id: string; doc_type: string; period_label: string | null; page_index: number; speaker?: string | null; published_at?: string | null; source_url?: string; content_hash?: string };
export type NotebookDraft = { symbol: string; company: string; kind: "cited_point" | "source_quote" | "follow_up"; text: string; question?: string | null; cutoff?: string | null; mode: string; evidence?: Record<string, EvidenceIndexEntry> };
type Entry = Omit<NotebookDraft, "evidence"> & { id: string; key: string; saved_at: string; origin_url: string; sources: Source[]; note: string; status: "open" | "done" };
type NotebookState = { items: Entry[]; storageError: boolean; save: (draft: NotebookDraft) => Promise<void>; update: (id: string, values: Partial<Pick<Entry, "note" | "status">>) => void; remove: (id: string) => void };
const KEY = "finn.notebook.v1";
const Context = createContext<NotebookState | null>(null);
const draftKey = (draft: NotebookDraft) => JSON.stringify([draft.symbol, draft.kind, draft.text, draft.cutoff, Object.keys(draft.evidence || {}).sort()]);

function read(): { items: Entry[]; failed: boolean } {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) || "[]");
    const items = Array.isArray(value) ? value.filter((v): v is Entry => v && typeof v.id === "string" && typeof v.key === "string" && typeof v.text === "string" && typeof v.symbol === "string" && Array.isArray(v.sources)).slice(0, 100) : [];
    return { items, failed: false };
  } catch { return { items: [], failed: true }; }
}

export function NotebookProvider({ children }: { children: ReactNode }) {
  const [initial] = useState(read);
  const [items, setItems] = useState<Entry[]>(initial.items);
  const [storageError, setStorageError] = useState(initial.failed);
  useEffect(() => {
    try { localStorage.setItem(KEY, JSON.stringify(items)); setStorageError(false); }
    catch { setStorageError(true); }
  }, [items]);
  const save = async (draft: NotebookDraft) => {
    if (items.some((entry) => entry.key === draftKey(draft))) return;
    if (items.length >= 100) throw new Error("Your notebook has 100 items. Export it, then remove an item before saving another.");
    const sources: Source[] = await Promise.all(Object.entries(draft.evidence || {}).map(async ([id, source]) => {
      const base: Source = { passage_id: id, version_id: source.version_id, doc_type: source.doc_type, period_label: source.period_label, page_index: source.page_index, speaker: source.speaker, published_at: source.published_at };
      try {
        const evidence = await api.evidence(id);
        return { ...base, source_url: evidence.document.source_url, content_hash: evidence.document.content_hash };
      } catch { return base; }
    }));
    const { evidence: _evidence, ...record } = draft;
    const entry: Entry = { ...record, id: crypto.randomUUID(), key: draftKey(draft), saved_at: new Date().toISOString(), origin_url: window.location.href, sources, note: "", status: "open" };
    setItems((current) => current.some((v) => v.key === entry.key) ? current : [entry, ...current].slice(0, 100));
  };
  return <Context.Provider value={{ items, storageError, save, update: (id, values) => setItems((current) => current.map((item) => item.id === id ? { ...item, ...values } : item)), remove: (id) => setItems((current) => current.filter((item) => item.id !== id)) }}>{children}</Context.Provider>;
}

function useNotebook() {
  const context = useContext(Context);
  if (!context) throw new Error("NotebookProvider is required");
  return context;
}

export function SaveToNotebook({ draft, label = "Save point" }: { draft: NotebookDraft; label?: string }) {
  const notebook = useNotebook();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saved = notebook.items.some((entry) => entry.key === draftKey(draft));
  return <span className="notebook-save">
    <button type="button" className="btn btn-small btn-ghost" disabled={saving} onClick={async () => {
      if (saved) { window.location.hash = "/notebook"; return; }
      setSaving(true); setError(null);
      try { await notebook.save(draft); } catch (e) { setError(e instanceof Error ? e.message : "This point could not be saved."); }
      finally { setSaving(false); }
    }}>{saving ? "Saving…" : saved ? "Saved · open notebook" : label}</button>
    {error && <span className="composer-error" role="alert">{error}</span>}
  </span>;
}

export function NotebookSummary() {
  const { items } = useNotebook();
  return <Section title="Your research notebook" aside={<Chip tone="muted">{items.filter((entry) => entry.status === "open").length} open</Chip>}>
    <p className="fine">Keep cited points and your own follow-ups together. Saved only in this browser, with no login or upload.</p>
    <a className="btn btn-small" href="#/notebook">{items.length ? `Open ${items.length} saved item${items.length === 1 ? "" : "s"}` : "Open notebook"}</a>
  </Section>;
}

function markdown(items: Entry[]): string {
  return ["# FINN research notebook", "Exported " + new Date().toISOString(), "User notes are personal research annotations, separate from the cited company evidence.", ...items.flatMap((item) => [
    `## ${item.symbol} - ${item.kind.replace(/_/g, " ")}`,
    item.company, `Status: ${item.status} | Saved: ${item.saved_at}`, `Source mode: ${item.mode} | Evidence cutoff: ${item.cutoff || "not supplied"}`,
    item.question ? `Question: ${item.question}` : "", item.kind === "source_quote" ? `> ${item.text.replace(/\n/g, "\n> ")}` : item.text,
    ...item.sources.map((source) => `- ${docLabel(source.doc_type, source.period_label)}, PDF page ${source.page_index}${source.speaker ? `; speaker: ${source.speaker}` : ""}${source.published_at ? `; published ${source.published_at}` : ""}; passage ${source.passage_id}${source.source_url ? `; ${source.source_url}` : "; original URL unavailable"}${source.content_hash ? `; SHA-256 ${source.content_hash}` : ""}`),
    `Original FINN view: ${item.origin_url}`, item.note ? `### My follow-up / note\n${item.note}` : "", "",
  ])].filter(Boolean).join("\n\n");
}

export function NotebookView() {
  const { items, update, remove, storageError } = useNotebook();
  const [filter, setFilter] = useState("open");
  const [query, setQuery] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const visible = items.filter((item) => (filter === "all" || item.status === filter) && `${item.symbol} ${item.company} ${item.text} ${item.note}`.toLowerCase().includes(query.trim().toLowerCase()));
  const exportItems = () => {
    const url = URL.createObjectURL(new Blob([markdown(items)], { type: "text/markdown;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = `FINN_Notebook_${new Date().toISOString().slice(0, 10)}.md`; a.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <div className="stack">
    <section className="card">
      <div className="eyebrow">Your workspace</div><h1>Research notebook</h1>
      <p className="muted">Cited points worth returning to, with your own follow-up notes. Nothing here is sent to an AI service.</p>
      <p className="fine">Stored only in this browser on this device. It does not sync between the demo and live app. Export before clearing browser data.</p>
      {storageError && <p className="composer-error" role="alert">Browser storage is unavailable. This notebook lasts only while this tab stays open; export it to keep your work.</p>}
      <div className="event-actions"><button className="btn btn-small" disabled={!items.length} onClick={exportItems}>Export Markdown ({items.length})</button><a className="btn btn-small btn-ghost" href="#/research">Find a company</a></div>
      <label className="notebook-search">Search your notebook<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Company, point or note" maxLength={100} /></label>
      <div className="attention-options" role="group" aria-label="Notebook status">{[["open", "To follow up"], ["done", "Done"], ["all", "All"]].map(([value, label]) => <button key={value} className={`btn btn-small${filter === value ? " selected" : ""}`} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
    </section>
    {!visible.length && <Section title={items.length ? "No items in this view" : "Start with a useful point"}><p className="muted">{items.length ? "Try another status or search." : "Open a saved brief and select Save point or Save quote beside its evidence. You can also keep a question as a follow-up."}</p><a className="btn btn-small" href="#/research">Open company research</a></Section>}
    {visible.map((item) => <section className="card notebook-entry" key={item.id}>
      <div className="card-head"><div><a className="company-link" href={`#/c/${encodeURIComponent(item.symbol)}?mode=${item.mode === "live" ? "live" : "replay"}`}>{item.symbol}</a><span className="sub">{item.company}</span></div><Chip tone="muted">{item.kind === "source_quote" ? "Source quote" : item.kind === "follow_up" ? "Follow-up" : "Cited point"}</Chip></div>
      {item.question && item.question !== item.text && <p className="fine">Question: {item.question}</p>}
      <p className="notebook-point">{item.kind === "source_quote" ? `“${item.text}”` : item.text}</p>
      <p className="fine">{item.mode === "replay" ? "Historical" : "Current-source run"} · evidence by {item.cutoff ? istDateTime(item.cutoff) : "cutoff not supplied"} · saved {istDateTime(item.saved_at)}</p>
      {item.sources.length > 0 && <ul className="notebook-sources">{item.sources.map((source) => <li key={source.passage_id}>{source.source_url ? <a href={source.source_url + (/\.pdf(?:[?#]|$)/i.test(source.source_url) && !source.source_url.includes("#") ? `#page=${source.page_index}` : "")} target="_blank" rel="noopener noreferrer">{docLabel(source.doc_type, source.period_label)} · PDF p.{source.page_index}</a> : <span>{docLabel(source.doc_type, source.period_label)} · PDF p.{source.page_index}</span>}<span className="sub">Passage {source.passage_id}</span></li>)}</ul>}
      <div className="notebook-note"><label htmlFor={`note-${item.id}`}>My follow-up / note</label><textarea id={`note-${item.id}`} value={item.note} onChange={(event) => update(item.id, { note: event.target.value })} maxLength={2000} rows={3} placeholder="What should I verify or watch next?" /></div>
      <p className="fine">Your note is an annotation, separate from the company evidence. {item.note.length}/2000 characters.</p>
      <div className="event-actions"><button className="btn btn-small" onClick={() => update(item.id, { status: item.status === "open" ? "done" : "open" })}>{item.status === "open" ? "Mark followed up" : "Reopen follow-up"}</button><a className="btn btn-small btn-ghost" href={item.origin_url}>Return to source view</a><button className="btn btn-small btn-ghost" onClick={() => setDeleteId(item.id)}>Remove</button></div>
      {deleteId === item.id && <div className="notebook-confirm" role="group" aria-label="Confirm removal"><p className="fine">Remove this saved point and your note from this browser?</p><button className="btn btn-small" onClick={() => { remove(item.id); setDeleteId(null); }}>Remove item</button><button className="btn btn-small btn-ghost" onClick={() => setDeleteId(null)}>Keep item</button></div>}
    </section>)}
  </div>;
}
