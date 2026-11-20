#!/usr/bin/env python3
"""Check whether a fresh GitHub runner can read one current NSE announcement feed."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "app" / "backend"))

from finn.config import get_settings  # noqa: E402
from finn.db import Store  # noqa: E402
from finn.sources import nse  # noqa: E402
from finn.sources.fetch import Fetcher  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="finn-nse-probe-") as tmp:
        settings = get_settings()
        store = Store(Path(tmp) / "finn.sqlite3", Path(tmp) / "sources")
        fetcher = Fetcher(store, max_bytes=settings.max_download_bytes)
        result = None
        detail = None
        try:
            ok, detail = nse.refresh_security_master(store, fetcher)
            if ok:
                company = nse.resolve_company(store, "INFY")
                end = datetime.now(timezone.utc).date()
                response, _ = nse.fetch_announcements(fetcher, company, end - timedelta(days=1), end)
                result = {"ok": response.ok, "state": response.state, "http_status": response.http_status,
                          "host": response.final_url and urlparse(response.final_url).hostname}
            else:
                result = {"ok": False, "state": "security_master_unavailable", "detail": detail}
        except Exception as exc:  # the workflow switches to the documented Render fallback
            result = {"ok": False, "state": "probe_error", "detail": exc.__class__.__name__}
        finally:
            fetcher.close()
    print(json.dumps(result, sort_keys=True))
    return 0 if result and result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
