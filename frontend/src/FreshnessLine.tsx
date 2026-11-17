import type { ReactNode } from "react";
import { istDateTime } from "./format";

export type CheckRow = { symbol: string; state: string; error?: string | null; checked_at?: string | null; announcements?: number | null };
export type SourceChecks = { finished_at: string | null; holdings: CheckRow[]; last_full_check_at?: string | null };

export function checkAge(stamp: string, now = Date.now()) {
  const minutes = Math.max(0, Math.floor((now - Date.parse(stamp)) / 60000));
  return minutes < 1 ? "just now" : minutes < 60 ? `${minutes} min ago` : `${Math.floor(minutes / 60)} h ago`;
}

export function FreshnessLine({ checks, replay, action }: { checks?: SourceChecks; replay?: string; action?: ReactNode }) {
  const rows = checks?.holdings ?? [];
  const failed = rows.filter((row) => row.state !== "fetched" || !row.checked_at);
  const checked = rows.length - failed.length;
  const stamp = checks?.finished_at ?? null;
  const full = checks?.last_full_check_at ?? (checked > 0 && !failed.length ? stamp : null);
  const stale = stamp && Date.now() - Date.parse(stamp) > 36 * 3600000;
  return <div className="source-freshness freshness-line" aria-label="Filing source checks">
    {replay ? <p><strong>Historical replay</strong> · evidence by {replay}</p> : <>
      <p><strong>{!stamp ? "No current check recorded" : !checked ? "Exchange check unavailable" : failed.length ? "Partly checked" : "Checked"}</strong>
        {stamp && ` ${istDateTime(stamp)} · ${checked}/${rows.length} holdings · ${checkAge(stamp)}`}
        {stale && " · stale"}</p>
      {full && (full !== stamp || Date.now() - Date.parse(full) >= 24 * 3600000) &&
        <p className="fine">Last full check {checkAge(full)} ({istDateTime(full)}).</p>}
      {(!checked || !!failed.length || stale) && <p className="fine">Current coverage is incomplete. An absent filing is not an all-clear.</p>}
      {failed.length > 0 && <ul className="freshness-gaps">{failed.map((row) => <li key={row.symbol}><strong>{row.symbol}</strong> · not checked{row.state === "not_checked" ? "" : ` (${row.state})`}{row.error && <span className="sub">{row.error}</span>}</li>)}</ul>}
    </>}
    <details>
      <summary>Sources and checks</summary>
      <a className="btn btn-small" href="#/trust">Source coverage and quality</a>
      {action}
      {checked > 0 && <ul className="freshness-gaps">{rows.filter((row) => row.state === "fetched" && row.checked_at).map((row) => <li key={row.symbol}>{row.symbol} · checked {istDateTime(row.checked_at!)}</li>)}</ul>}
    </details>
  </div>;
}
