#!/usr/bin/env python3
"""Render-backed GitHub scheduler path for phone alerts when runner NSE access fails.

The existing Render API performs the bounded NSE source refresh. This client only
reads FINN's existing Review and Yahoo EOD read models, then sends via ntfy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from finn import alerts  # noqa: E402


def _request_json(base_url: str, path: str, method: str = "GET", retries: int = 5):
    url = base_url.rstrip("/") + path
    last = None
    for attempt in range(retries):
        try:
            req = Request(url, data=b"{}" if method == "POST" else None,
                          headers={"Accept": "application/json", "Content-Type": "application/json"}, method=method)
            with urlopen(req, timeout=180) as response:
                body = response.read(5 * 1024 * 1024 + 1)
            if len(body) > 5 * 1024 * 1024:
                raise ValueError("FINN response exceeded the 5 MB limit")
            return json.loads(body.decode("utf-8"))
        except HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code not in (408, 429, 500, 502, 503, 504):
                break
        except (URLError, TimeoutError, ValueError, UnicodeError) as exc:
            last = exc.__class__.__name__
        if attempt + 1 < retries:
            time.sleep(min(10 * (attempt + 1), 30))
    raise RuntimeError(f"FINN service request failed: {last or 'unavailable'}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("FINN_BASE_URL", "https://finn-mow9.onrender.com"))
    parser.add_argument("--state", required=True)
    parser.add_argument("--out-state", required=True)
    parser.add_argument("--out-status", required=True)
    parser.add_argument("--prices", required=True)
    parser.add_argument("--days", type=int, default=7, choices=range(1, 8))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    parsed = urlparse(args.base_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        parser.error("--base-url must be a public HTTPS URL")

    # Wake a free Render instance first; repeat for its cold-start window.
    _request_json(args.base_url, "/api/health")
    query = urlencode({"days": args.days})
    refresh = _request_json(args.base_url, f"/api/portfolio/refresh?{query}", method="POST")
    queue = _request_json(args.base_url, "/api/portfolio?" + urlencode({"mode": "live", "window": "7d"}))
    prices_path = Path(args.prices)
    prices = json.loads(prices_path.read_text()) if prices_path.is_file() else {}
    checked = {row.get("symbol") for row in refresh.get("companies", []) if row.get("state") == "fetched"}
    candidates = alerts.build_notifications(queue, prices, checked_symbols=checked,
                                           extra_categories=alerts.categories_from_env(),
                                           now=datetime.now(timezone.utc), days=args.days)
    state_path, out_state = Path(args.state), Path(args.out_state)
    state = alerts.load_state(state_path)
    pending = alerts.pending_notifications(candidates, state)
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    dry_run = args.dry_run or not topic
    outcomes = {"sent": [], "failed": [], "filing_delay_seconds": []}
    if not dry_run:
        next_state, outcomes = alerts.send_pending(pending, state, topic=topic)
        alerts.save_state(out_state, next_state)
    else:
        # Preserve prior de-duplication state. The job can show a dry-run summary
        # without accidentally consuming any alerts before the owner configures ntfy.
        alerts.save_state(out_state, state)

    status = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "refresh_state": refresh.get("state"), "holdings_checked": refresh.get("checked", 0),
              "holdings_total": len(refresh.get("companies", [])), "pending": len(pending),
              "sent": len(outcomes["sent"]), "failed": len(outcomes["failed"]),
              "filing_delay_seconds": outcomes["filing_delay_seconds"],
              "dry_run": dry_run,
              "delivery": "topic_not_configured" if not topic else ("dry_run" if args.dry_run else "ntfy"),
              "cadence_note": "GitHub's free scheduler is best-effort; checks may be minutes to hours apart."}
    status_path = Path(args.out_status)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))
    if dry_run:
        for item in pending:
            print(f"DRY RUN · {item['title']} · {item['key']}")
    return 2 if outcomes["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
