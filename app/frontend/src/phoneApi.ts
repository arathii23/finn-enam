import { IS_STATIC } from "./api";
import { liveAppUrl } from "./links";

export type PhoneSubscription = {
  symbols: string[]; groups: string[]; active: boolean; topic: string;
  created_at: string; updated_at: string; enabled_at: string | null; test_accepted_at: string | null;
  last_delivery_at: string | null;
  test_requested_at: string | null; test_state: "queued" | "accepted" | null; test_error: string | null;
  last_items: { symbol: string; title: string; body: string; published_at: string; filing_url: string | null; company_url: string }[];
};
export type PhoneCatalog = {
  available: boolean; companies: { symbol: string; name: string }[];
  groups: { id: string; label: string; description: string }[];
  cadence: string; max_daily: number;
  test_cadence: string;
  last_check: { checked_at: string; holdings_checked: number; holdings_total: number; unchecked_symbols?: string[] } | null;
};

export class PhoneApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

const origin = IS_STATIC ? new URL(liveAppUrl()).origin : "";
async function request<T>(path: string, token?: string, method = "GET", body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 65000);
  try {
    const response = await fetch(`${origin}/api/phone/${path}`, {
      method, cache: "no-store", credentials: "omit", signal: controller.signal,
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body ? { "Content-Type": "application/json" } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new PhoneApiError(response.status,
      typeof result?.detail === "string" ? result.detail : "Phone alerts could not be reached. Please try again.");
    return result as T;
  } catch (error) {
    if (error instanceof PhoneApiError) throw error;
    throw new PhoneApiError(0, "The free alert service may be waking up. Wait a minute, then try again.");
  } finally { window.clearTimeout(timeout); }
}

export const phoneApi = {
  catalog: () => request<PhoneCatalog>("catalog"),
  get: (token: string) => request<PhoneSubscription>("subscription", token),
  save: (token: string, symbols: string[], groups: string[], active: boolean) =>
    request<PhoneSubscription>("subscription", token, "PUT", { symbols, groups, active }),
  test: (token: string) => request<{ accepted: boolean; queued: boolean }>("test", token, "POST"),
  delete: (token: string) => request<{ deleted: boolean }>("subscription", token, "DELETE"),
};

const storageKey = "finn.phone.v1";
export function readPhoneToken(): string | null {
  try {
    const value = localStorage.getItem(storageKey);
    return value && /^[A-Za-z0-9_-]{43}$/.test(value) ? value : null;
  } catch { return null; }
}
export function savePhoneToken(token: string) {
  try { localStorage.setItem(storageKey, token); }
  catch { throw new Error("Allow browser storage before setting up alerts so you can manage or stop them later."); }
}
export function clearPhoneToken() { localStorage.removeItem(storageKey); }
export function createPhoneToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
