import { useEffect, useState } from "react";
import { api, type SavedResearchItem } from "./api";
import { istDateTime } from "./format";
import { Chip, Section } from "./ui";
import "./research.css";

export function SavedResearch({ symbol }: { symbol?: string }) {
  const [items, setItems] = useState<SavedResearchItem[] | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setItems(null); setError(false);
    api.savedResearch(symbol).then((result) => { if (live) setItems(result.items); }).catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [symbol, attempt]);
  return (
    <Section title="Saved research" aside={<Chip tone="muted">Read without a new run</Chip>}>
      {error ? <><p className="muted">Saved research could not be loaded.</p><button className="btn btn-small" onClick={() => setAttempt(attempt + 1)}>Retry saved research</button></>
        : !items ? <p className="muted" role="status">Loading saved research…</p>
          : items.length === 0 ? <p className="muted">No saved research{symbol ? ` for ${symbol}` : ""} yet. Run a company overview or ask a focused question.</p>
            : <ul className="saved-research-list">{items.map((item) => (
              <li key={item.job_id}>
                <a className="saved-research-link" href={`#/c/${encodeURIComponent(item.symbol)}/research/${encodeURIComponent(item.job_id)}`}>
                  <span className="saved-research-title">{!symbol && <strong>{item.symbol} · </strong>}{item.question || "Company overview"}</span>
                  <span className="sub">{!symbol && `${item.legal_name} · `}{item.document_count} source documents</span>
                  <span className="sub">Prepared {istDateTime(item.generated_at)}</span>
                  <span className="saved-research-cta">Read saved research →</span>
                </a>
              </li>
            ))}</ul>}
    </Section>
  );
}
