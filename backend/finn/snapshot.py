"""Export a static, read-only snapshot of the verified corpus.

The snapshot is a folder of plain JSON that the React app can serve from any CDN with NO
backend: the full Push digest, every saved research brief, the keyless source briefs,
quarterly tables, management cards, narrative-vs-numbers and exact evidence — all read-only,
all from the same data the live server would return. It is built with model keys treated as
absent, so nothing here depends on, or spends on, a model. On-demand (Pull) research and
threshold re-tuning need the live backend and are disabled in the static build, clearly.

Evidence links point to the ORIGINAL source documents (NSE / screener.in / company IR), so
the bundle stays small and every figure remains independently verifiable by its hash.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set

from .db import utcnow
from .service import App, NotFound
from .sources import nse


def _write(out: Path, name: str, payload: Any) -> Any:
    (out / name).write_text(json.dumps(payload, default=str))
    return payload


def _collect_evidence_ids(obj: Any, acc: Set[str]) -> None:
    """Recursively gather passage ids that are actually CLICKABLE (have an Evidence button).

    The full ``evidence_index`` is only a label lookup; exporting a file for every packet
    passage would bloat the snapshot with thousands of never-opened files. We export evidence
    only for ids referenced by a claim, brief highlight, gap, follow-up, quarterly metric,
    appointment/profile card or the keyless passage fallback.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "evidence_index":
                continue  # lookup table, not clickable targets
            if k in ("evidence_id", "appointment_evidence_id", "profile_evidence_id") and isinstance(v, str):
                acc.add(v)
            elif k in ("evidence_ids", "candidate_evidence_ids") and isinstance(v, list):
                acc.update(x for x in v if isinstance(x, str))
            else:
                _collect_evidence_ids(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect_evidence_ids(v, acc)


def export_static(app: App, out_dir: Path) -> Dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.json"):
        stale.unlink()

    assert not app.settings.model_configured, "Static snapshot must be exported with model keys unset."
    evidence_ids: Set[str] = set()
    payloads: List[Any] = []

    payloads.append(_write(out, "health.json", app.health()))
    for window in ("24h", "7d", "all"):
        payloads.append(_write(out, f"portfolio_{window}.json", app.portfolio_queue(mode="replay", window=window)))

    symbols: List[str] = []
    for symbol in app.portfolio.get("symbols", []):
        try:
            nse.resolve_company(app.store, symbol)
        except nse.IdentityError:
            continue
        symbols.append(symbol)
        for name, fn in (("overview", app.company_overview), ("narrative", app.narrative_numbers),
                         ("quarterly", app.quarterly_results), ("management", app.management_changes)):
            try:
                payloads.append(_write(out, f"{name}_{symbol}.json", fn(symbol)))
            except NotFound as exc:
                _write(out, f"{name}_{symbol}.json", {"error": exc.state, "message": str(exc)})

    saved = _write(out, "saved.json", app.saved_research())
    payloads.append(saved)
    for symbol in symbols:
        per = app.saved_research(symbol)
        if per["items"]:
            _write(out, f"saved_{symbol}.json", per)
    for item in saved["items"]:
        job = app.job(item["job_id"])
        payloads.append(_write(out, f"job_{item['job_id']}.json", job))

    for p in payloads:
        _collect_evidence_ids(p, evidence_ids)
    exported_ev = 0
    for pid in sorted(evidence_ids):
        try:
            _write(out, f"evidence_{pid}.json", app.evidence(pid))
            exported_ev += 1
        except NotFound:
            continue

    # version_id -> original document URL, so static evidence/filing links resolve off-site.
    docs = {}
    for row in app.store.query("SELECT version_id, source_url, final_url, host FROM document_versions"):
        docs[row["version_id"]] = {"source_url": row["source_url"], "final_url": row.get("final_url"), "host": row["host"]}
    _write(out, "documents.json", docs)

    manifest = {
        "snapshot_version": 1,
        "generated_at": utcnow(),
        "replay": app.replay_info(),
        "portfolio_symbols": symbols,
        "counts": {"companies": len(symbols), "saved_research": len(saved["items"]),
                   "evidence_passages": exported_ev, "documents": len(docs)},
        "scope": "Read-only static snapshot. On-demand research and threshold re-tuning require the live backend.",
    }
    _write(out, "manifest.json", manifest)
    return manifest
