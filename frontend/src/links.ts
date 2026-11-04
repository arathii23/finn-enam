import type { ResearchMode } from "./api";

type ResearchLink = { symbol?: string; question?: string | null; eventId?: string | null; mode?: ResearchMode };

export function researchPath({ symbol, question, eventId, mode = "replay" }: ResearchLink = {}): string {
  const params = new URLSearchParams({ mode });
  if (question?.trim()) params.set("question", question.trim().slice(0, 300));
  if (eventId) params.set("event", eventId);
  return `${symbol ? `/c/${encodeURIComponent(symbol.toUpperCase())}` : "/research"}?${params}`;
}

// A handoff is a normal link. No research request or source text is sent until the user opens
// the live app and explicitly asks a question there. Never put keys or notes in a URL.
export function liveAppUrl(context: ResearchLink = {}): string {
  const fallback = "https://finn-mow9.onrender.com";
  let base: URL;
  try {
    base = new URL(import.meta.env.VITE_LIVE_APP_URL || fallback);
    if (base.protocol !== "https:" || base.username || base.password) throw new Error("Invalid live app URL");
  } catch { base = new URL(fallback); }
  base.search = "";
  base.hash = researchPath(context);
  return base.toString();
}
