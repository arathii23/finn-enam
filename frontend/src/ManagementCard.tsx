import { useEffect, useState } from "react";
import { api, type ManagementChanges } from "./api";
import { istDateTime } from "./format";
import { Chip, EvidenceButton, Section } from "./ui";

export function ManagementCard({ symbol, onEvidence }: {
  symbol: string; onEvidence: (id: string, el: HTMLElement) => void;
}) {
  const [data, setData] = useState<ManagementChanges | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setData(null); setError(false);
    api.management(symbol).then((r) => live && setData(r)).catch(() => live && setError(true));
    return () => { live = false; };
  }, [symbol, attempt]);

  if (error) return <Section title="Management change"><p className="muted">Appointment context could not be loaded.</p><button className="btn btn-small" onClick={() => setAttempt(attempt + 1)}>Retry</button></Section>;
  if (!data) return <Section title="Management change"><p className="muted" role="status">Checking appointment filings…</p></Section>;
  if (!data.items.length) return null;
  return (
    <Section title="Management change" aside={<Chip tone="neutral">Primary filing</Chip>}>
      <div className="management-list">
        {data.items.map((item) => (
          <article className="management-item" key={item.announcement_id}>
            <p className="fine">Filed {istDateTime(item.published_at)}{!item.in_review_window && " · Before review window"}</p>
            <h3>{item.name}</h3>
            <p className="management-role">{item.role}</p>
            <p className="fine">{item.change} · Effective {item.effective_date_text}</p>
            <div className="ev-row"><EvidenceButton id={item.appointment_evidence_id} label={`Appointment · PDF p.${item.appointment_page_index}`} onOpen={onEvidence} /></div>
            <p className="management-label">From the appointment filing</p>
            <blockquote className="management-profile">{item.profile_quote}</blockquote>
            <div className="ev-row">
              <EvidenceButton id={item.profile_evidence_id} label={`Profile · PDF p.${item.profile_page_index}`} onOpen={onEvidence} />
              <a className="btn btn-small btn-ghost" href={api.fileUrl(item.version_id)} target="_blank" rel="noopener">Open appointment PDF</a>
            </div>
          </article>
        ))}
      </div>
      <p className="fine">Selected from stored filings available by the cutoff; not a complete management history.</p>
    </Section>
  );
}
