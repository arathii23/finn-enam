const IST = "Asia/Kolkata";

export function istDateTime(iso: string | null | undefined, precision?: "second" | "date" | null): string {
  if (!iso) return "unknown";
  const d = new Date(iso);
  if (precision === "date") {
    return d.toLocaleDateString("en-IN", { timeZone: IST, day: "numeric", month: "short", year: "numeric" }) + " (date only)";
  }
  return d.toLocaleString("en-IN", {
    timeZone: IST, day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }) + " IST";
}

export function marketDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-IN", { timeZone: "UTC", weekday: "short", day: "numeric", month: "short", year: "numeric" });
}

export function shortDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-IN", { timeZone: "UTC", day: "numeric", month: "short", year: "numeric" });
}

export const DOC_LABEL: Record<string, string> = {
  annual_report: "Annual report",
  earnings_call_transcript: "Earnings-call transcript",
  exchange_filing: "Exchange filing",
};

export function docLabel(t: string, period?: string | null): string {
  return `${DOC_LABEL[t] ?? t}${period ? ` · ${period}` : ""}`;
}

export function inr(n: number | null): string {
  return n == null ? "—" : n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function qty(n: number | null): string {
  return n == null ? "—" : n.toLocaleString("en-IN");
}

export function host(url: string): string {
  try { return new URL(url).host; } catch { return url; }
}
