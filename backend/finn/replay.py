"""Replay manifest loading and the publication-cutoff filter.

The filter runs BEFORE retrieval/generation: documents that were not provably public by the
cutoff never reach the passage search or the model."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .db import Store


@dataclass(frozen=True)
class ReplayConfig:
    replay_id: str
    label: str
    filing_from: str
    filing_to: str
    cutoff_utc: str
    cutoff_display: str
    raw: Dict[str, Any]


def load_manifest(path: Path) -> ReplayConfig:
    raw = json.loads(Path(path).read_text())
    cutoff = datetime.fromisoformat(raw["evidence_cutoff"]).astimezone(timezone.utc).isoformat()
    return ReplayConfig(
        replay_id=raw["replay_id"], label=raw["label"],
        filing_from=raw["filing_window"]["from"], filing_to=raw["filing_window"]["to"],
        cutoff_utc=cutoff, cutoff_display=raw.get("evidence_cutoff_display", raw["evidence_cutoff"]),
        raw=raw,
    )


def _ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def classify_versions(store: Store, company_id: str, mode: str, cutoff_utc: Optional[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (eligible, excluded-with-reasons) document versions for a company and mode."""
    rows = store.query("SELECT * FROM document_versions WHERE company_id=? ORDER BY published_at DESC", (company_id,))
    eligible, excluded = [], []
    cutoff = _ts(cutoff_utc) or (datetime.now(timezone.utc) if mode == "live" else None)
    for row in rows:
        ident = json.loads(row["identification"] or "{}")
        reasons = []
        if row["parse_status"] == "failed":
            reasons.append("text extraction failed")
        if not ident.get("identity_ok", False):
            reasons.append("document identity check failed")
        if row["availability_status"] != "verified" or not row["published_at"]:
            reasons.append("publication availability unverified")
        elif cutoff is not None and _ts(row["published_at"]) > cutoff:
            reasons.append("published after replay cutoff" if mode == "replay" else "published after source-check cutoff")
        target = excluded if reasons else eligible
        target.append({**row, "identification": ident, "exclusion_reasons": reasons})
    return eligible, excluded


def announcements_in_window(store: Store, company_id: str, cfg: Optional[ReplayConfig]) -> List[Dict[str, Any]]:
    rows = store.query("SELECT * FROM announcements WHERE company_id=? ORDER BY published_at DESC", (company_id,))
    if cfg is None:
        return rows
    start = datetime.fromisoformat(cfg.filing_from + "T00:00:00+05:30").astimezone(timezone.utc)
    end = datetime.fromisoformat(cfg.filing_to + "T23:59:59+05:30").astimezone(timezone.utc)
    cutoff = _ts(cfg.cutoff_utc)
    out = []
    for r in rows:
        t = _ts(r["published_at"])
        if t is not None and start <= t <= end and t <= cutoff:
            out.append(r)
    return out
