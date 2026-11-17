#!/usr/bin/env python3
"""Ask FINN to check current sources and deliver opt-in subscriber alerts.

The runner receives only aggregate counts. Subscriber settings and ntfy topics
stay in the private Redis store and never pass through GitHub artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlparse

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("FINN_BASE_URL", "https://finn-mow9.onrender.com"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname:
        parser.error("Use FINN's HTTPS backend URL.")
    token = os.environ.get("FINN_PHONE_ALERTS_JOB_TOKEN", "")
    if not token:
        parser.error("Set the scheduler's FINN_PHONE_ALERTS_JOB_TOKEN secret.")
    try:
        with httpx.Client(timeout=httpx.Timeout(560, connect=20), follow_redirects=False) as client:
            response = client.post(args.base_url.rstrip("/") + "/api/phone/dispatch",
                                   params={"dry_run": str(args.dry_run).lower()},
                                   headers={"Authorization": f"Bearer {token}"})
        if response.status_code != 200:
            print(f"FINN phone check returned HTTP {response.status_code}. No subscriber details are logged.")
            return 1
        result = response.json()
        print(json.dumps(result, indent=2))
        return 1 if result.get("failed") or ("holdings_checked" in result and not result["holdings_checked"]) else 0
    except (httpx.HTTPError, ValueError):
        print("FINN's phone check could not finish. Inspect the service health before retrying.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
