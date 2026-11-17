import { useEffect, useState } from "react";
import { istDateTime } from "./format";
import { Section } from "./ui";

type AlertStatus = { checked_at: string; holdings_checked: number; holdings_total: number; dry_run: boolean };
const statusUrl = "https://raw.githubusercontent.com/arathii23/finn-enam/live-data/alerts_status.json";
const calendarUrl = new URL("finn-events.ics", statusUrl).href;
// This asset and URL are intentionally public and only exist once the owner approves publication.
export function AlertsCard() {
  const [status, setStatus] = useState<AlertStatus | null>(null);
  const [topicUrl, setTopicUrl] = useState<string | null>(null);
  const [calendarAvailable, setCalendarAvailable] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch(statusUrl, { signal: controller.signal, cache: "no-cache" })
      .then((r) => r.ok ? r.json() : null)
      .then((value) => { if (typeof value?.checked_at === "string") setStatus(value); })
      .catch(() => {});
    fetch(`${import.meta.env.BASE_URL}alerts-subscription.json`, { signal: controller.signal })
      .then((r) => r.ok ? r.json() : null)
      .then((value) => {
        if (typeof value?.topic === "string" && /^[a-zA-Z0-9_-]{1,64}$/.test(value.topic)) {
          setTopicUrl(`https://ntfy.sh/${value.topic}`);
        }
      })
      .catch(() => {});
    fetch(calendarUrl, { method: "HEAD", signal: controller.signal })
      .then((r) => setCalendarAvailable(r.ok))
      .catch(() => {});
    return () => controller.abort();
  }, []);
  return <Section title="Alerts">
    <p>Get leading company filings and end-of-day threshold flags on your phone when alerts are enabled.</p>
    {topicUrl ? <div className="alert-subscribe">
      <a className="btn btn-small" href={topicUrl} target="_blank" rel="noopener noreferrer">Open ntfy topic</a>
      <img width="120" height="120" src={`${import.meta.env.BASE_URL}alerts-qr.png`} alt="QR code for the public FINN alerts topic" />
    </div> : <p className="fine">Phone delivery is awaiting setup.</p>}
    <p className="fine">GitHub’s scheduler can run minutes to hours apart. End-of-day flags use portfolio defaults.</p>
    <p className="fine">{status ? `Last scheduled check ${istDateTime(status.checked_at)} · ${status.holdings_checked}/${status.holdings_total} holdings checked${status.dry_run ? " · dry run" : ""}.` : "No scheduled check time is available."}</p>
    {calendarAvailable && <p><a href={calendarUrl} className="btn btn-small">Open NSE calendar feed</a></p>}
  </Section>;
}
