#!/usr/bin/env python3
"""Deliver private subscriber queues from GitHub's free public-repo runner.

Render supplies the shared NSE read model. The worker reads preferences directly
from private Redis and publishes to ntfy, avoiding Render's shared visitor limit.
Only aggregate counts are logged.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'app' / 'backend'))
from finn.config import get_settings
from finn.phone_alerts import PhoneAlerts, PhoneError, RedisPhoneStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default=os.environ.get('FINN_BASE_URL', 'https://finn-mow9.onrender.com'))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--scheduled', action='store_true')
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or not parsed.hostname:
        parser.error("Use FINN's HTTPS backend URL.")
    settings = get_settings()
    if not settings.phone_redis_url or not settings.phone_redis_token:
        parser.error('Set the private Upstash REST URL and token as Actions secrets.')
    companies = json.loads(settings.portfolio_path.read_text())['symbols']
    store = RedisPhoneStore(settings.phone_redis_url, settings.phone_redis_token)
    manager = PhoneAlerts(store, [{'symbol': symbol, 'name': symbol} for symbol in companies])
    try:
        with httpx.Client(timeout=120, follow_redirects=False) as client:
            def source(path, method='GET'):
                response = client.request(method, args.base_url.rstrip('/') + path)
                response.raise_for_status()
                return response.json()
            result = manager.check(lambda: source('/api/portfolio/refresh?days=7', 'POST'),
                                   lambda: source('/api/portfolio?mode=live&window=7d'),
                                   dry_run=args.dry_run, scheduled=args.scheduled)
        tests, filings = result['tests'], result['filings']
        print(json.dumps(result, indent=2))
        return 1 if tests['failed'] or filings.get('failed') or ('holdings_checked' in filings and not filings['holdings_checked']) else 0
    except (PhoneError, httpx.HTTPError, ValueError):
        print('The subscriber worker could not finish. Saved preferences and pending requests remain in Redis.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
