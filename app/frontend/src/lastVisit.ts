const KEY = "finn.lastVisit.v1";
type Versions = Record<string, string>;
export type Visit = { watermark: string | null; seen: Versions; cleared: Versions; updated: string | null };
const blank = (): Visit => ({ watermark: null, seen: {}, cleared: {}, updated: null });
type Item = { id: string; version: string };

function versions(value: unknown): Versions {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(Object.entries(value).filter(([id, version]) => /^ann_[a-zA-Z0-9_-]+$/.test(id) && typeof version === "string" && /^[a-f0-9]{16}$/.test(version)).slice(-500));
}

export function readVisit(): { visit: Visit; unavailable: boolean } {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { visit: blank(), unavailable: false };
    let item;
    try { item = JSON.parse(raw); } catch { return { visit: blank(), unavailable: false }; }
    const validDate = (value: unknown) => typeof value === "string" && Number.isFinite(Date.parse(value));
    return { visit: { watermark: validDate(item?.watermark) ? item.watermark : null,
      seen: versions(item?.seen), cleared: versions(item?.cleared), updated: validDate(item?.updated) ? item.updated : null }, unavailable: false };
  } catch {
    return { visit: blank(), unavailable: true };
  }
}

export function writeVisit(visit: Visit) {
  try {
    localStorage.setItem(KEY, JSON.stringify(visit));
    return true;
  } catch {
    return false;
  }
}

export function markOne(visit: Visit, item: Item): Visit {
  return { ...visit, seen: versions({ ...visit.seen, [item.id]: item.version }), updated: new Date().toISOString() };
}

export function markAll(visit: Visit, items: Item[], generated: string): Visit {
  const cleared = { ...visit.cleared };
  for (const item of items) {
    delete cleared[item.id];
    cleared[item.id] = item.version;
  }
  return { watermark: !visit.watermark || Date.parse(generated) >= Date.parse(visit.watermark) ? generated : visit.watermark,
    cleared: versions(cleared), seen: {}, updated: new Date().toISOString() };
}

export function wasCleared(visit: Visit, item: Item) {
  return visit.cleared[item.id] === item.version;
}
