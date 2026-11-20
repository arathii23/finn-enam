import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Evidence } from "./api";
import { docLabel, host, istDateTime } from "./format";
import { StateBox } from "./ui";

export function EvidenceSheet({ passageId, onClose }: { passageId: string; onClose: () => void }) {
  const [data, setData] = useState<Evidence | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let live = true;
    setData(null); setError(null);
    api.evidence(passageId).then((d) => live && setData(d)).catch((e) => live && setError(e));
    return () => { live = false; };
  }, [passageId]);

  useEffect(() => {
    closeRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key !== "Tab") return;
      const controls = sheetRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled]), [tabindex="0"]');
      if (!controls?.length) return;
      const first = controls[0], last = controls[controls.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = previousOverflow; };
  }, [onClose]);

  const doc = data?.document;
  const ev = doc?.availability_evidence?.find((x) => x.matched_record) ?? doc?.availability_evidence?.[0];

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div ref={sheetRef} className="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-head">
          <h2 id="sheet-title">Evidence</h2>
          <button ref={closeRef} type="button" className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
        {!data && !error && <StateBox kind="loading" title="Loading passage and document metadata…" />}
        {error && <StateBox kind="error" title="Evidence could not be loaded">{error.message}</StateBox>}
        {data && doc && (
          <>
            <dl className="meta">
              <dt>Company</dt><dd>{data.company.legal_name} · {data.company.symbol}</dd>
              <dt>Document</dt><dd>{docLabel(doc.doc_type, doc.period_label)}</dd>
              <dt>Published</dt>
              <dd>
                {istDateTime(doc.published_at, doc.published_precision)}
                <span className="sub">{doc.availability_status === "verified" ? `Proof: ${ev?.method?.replace(/_/g, " ") ?? "recorded"}` : "Availability unverified"}</span>
              </dd>
              <dt>Location</dt>
              <dd>PDF page {data.passage.page_index} of {doc.page_count ?? "?"}
                <span className="sub">Printed page: {data.passage.printed_page ?? data.passage.printed_page_reason ?? "unknown"}</span></dd>
              {data.passage.speaker && (<><dt>Speaker</dt><dd>{data.passage.speaker}</dd></>)}
              <dt>Source</dt><dd>{host(doc.source_url)}<span className="sub">Retrieved {istDateTime(doc.retrieved_at)}</span></dd>
              <dt>Content hash</dt><dd className="mono">sha256:{doc.content_hash.slice(0, 16)}…</dd>
            </dl>
            <blockquote className="passage">{data.passage.text}</blockquote>
            <p className="fine">Extracted text from the PDF page above. Layout, tables and footnotes may read differently in the original.</p>
            <div className="actions">
              <a className="btn btn-primary" href={api.fileUrl(doc.version_id, data.passage.page_index)} target="_blank" rel="noopener">
                Open PDF at page {data.passage.page_index}
              </a>
              <a className="btn" href={doc.source_url} target="_blank" rel="noopener noreferrer">Open original ({host(doc.source_url)})</a>
            </div>
            <p className="fine">If your browser ignores the page jump, scroll to PDF page {data.passage.page_index}.</p>
          </>
        )}
      </div>
    </div>
  );
}
