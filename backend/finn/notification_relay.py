"""Optional QStash relay with provider-confirmed receipts and durable retries."""
from __future__ import annotations

import hashlib
import json
import re
import time
from urllib.parse import urlparse

import httpx

from .alerts import ntfy_payload
from .phone_alerts import PhoneError

RECEIPT_PREFIX = 'finn:phone:relay:v1:'


class QStashRelay:
    def __init__(self, url, token, store, *, transport=None):
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or not re.fullmatch(r'qstash(?:-[a-z0-9-]+)?\.upstash\.io', parsed.hostname or '')
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/') or parsed.port not in (None, 443)):
            raise ValueError('Use the QStash HTTPS URL shown in the Upstash console.')
        self.url, self.token, self.store, self.transport = url.rstrip('/'), token, store, transport

    def __call__(self, topic, item):
        payload = ntfy_payload(topic, item)
        identity = hashlib.sha256((topic + '|' + str(item.get('key') or json.dumps(payload, sort_keys=True))).encode()).hexdigest()
        key = RECEIPT_PREFIX + identity
        headers = {'Authorization': 'Bearer ' + self.token}
        try:
            raw = self.store.command('GET', key)
            receipt = json.loads(raw) if raw else None
            if receipt and receipt.get('delivered'):
                return
            with httpx.Client(timeout=8, transport=self.transport, follow_redirects=False) as client:
                if receipt is None:
                    response = client.post(self.url + '/v2/publish/https://ntfy.sh', json=payload,
                                           headers={**headers, 'Upstash-Retries': '1', 'Upstash-Timeout': '15s',
                                                    'Upstash-Deduplication-Id': identity})
                    response.raise_for_status()
                    message_id = response.json().get('messageId')
                    if not isinstance(message_id, str) or not message_id:
                        raise ValueError('Missing relay message ID')
                    receipt = {'message_id': message_id, 'delivered': False}
                    self.store.command('SET', key, json.dumps(receipt), 'EX', 8 * 86400)
                deadline = time.monotonic() + 25
                for attempt in range(10):
                    response = client.get(self.url + '/v2/logs', params={'messageId': receipt['message_id'], 'count': 10}, headers=headers)
                    response.raise_for_status()
                    logs = response.json().get('logs', [])
                    states = {row.get('state') for row in logs if row.get('messageId') == receipt['message_id']}
                    if 'DELIVERED' in states:
                        receipt['delivered'] = True
                        self.store.command('SET', key, json.dumps(receipt), 'EX', 8 * 86400)
                        return
                    if states & {'FAILED', 'CANCELLED'}:
                        self.store.command('DEL', key)
                        raise PhoneError('The relay could not finish delivery. The alert remains pending.', 502)
                    if time.monotonic() >= deadline:
                        break
                    if attempt < 9:
                        time.sleep(2)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise PhoneError('The delivery relay is temporarily unavailable. Your notification remains pending.', 503) from exc
        raise PhoneError('The relay is still processing this notification. The next check will reuse its delivery receipt.', 503)
