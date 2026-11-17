#!/usr/bin/env python3
"""Create or update FINN's one QStash schedule without printing credentials."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from finn.config import get_settings
from finn.notification_relay import QStashRelay

SCHEDULE_ID = 'finn-followed-company-alerts'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='https://finn-mow9.onrender.com')
    parser.add_argument('--activate', action='store_true', help='Create/update the private five-minute timer')
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        parser.error('Use the public HTTPS backend origin.')
    settings = get_settings()
    if not settings.qstash_token or not settings.phone_job_token:
        parser.error('Add QSTASH_TOKEN and FINN_PHONE_ALERTS_JOB_TOKEN to the ignored local .env.')
    try:
        relay = QStashRelay(settings.qstash_url, settings.qstash_token, None)
        if not args.activate:
            print('Ready to configure one five-minute QStash schedule, with one retry and a fourteen-minute response timeout. No schedule was changed.')
            return 0
        destination = args.base_url.rstrip('/') + '/api/phone/tick'
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.post(relay.url + '/v2/schedules/' + destination, content='{}', headers={
                'Authorization': 'Bearer ' + settings.qstash_token,
                'Upstash-Schedule-Id': SCHEDULE_ID,
                'Upstash-Cron': '*/5 * * * *',
                'Upstash-Method': 'POST',
                'Upstash-Retries': '1',
                'Upstash-Timeout': '14m',
                'Upstash-Forward-Authorization': 'Bearer ' + settings.phone_job_token,
                'Content-Type': 'application/json',
            })
            response.raise_for_status()
            if response.json().get('scheduleId') != SCHEDULE_ID:
                raise ValueError('Unexpected schedule receipt')
        print('The private QStash timer is configured. Observe an automatic delivery check before claiming activation is verified.')
        return 0
    except (httpx.HTTPError, ValueError, AttributeError):
        print('The schedule could not be confirmed. Check the QStash URL/token and Free-plan setup in Upstash. Credentials were not logged.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
