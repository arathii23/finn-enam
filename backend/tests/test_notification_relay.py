"""Provider acceptance, pending receipts and safe relay failures."""
import json

import httpx
import pytest

from finn.notification_relay import QStashRelay
from finn.phone_alerts import PhoneError


class ReceiptStore:
    def __init__(self):
        self.values = {}

    def command(self, operation, key, *args):
        if operation == 'GET':
            return self.values.get(key)
        if operation == 'SET':
            self.values[key] = args[0]
            assert args[1:] == ('EX', 8 * 86400)
        elif operation == 'DEL':
            self.values.pop(key, None)
        else:
            pytest.fail('Unexpected Redis operation')


ITEM = {'key': 'test-1', 'title': 'FINN test', 'body': 'Selected: INFY',
        'company_url': 'https://arathii23.github.io/finn-enam/'}


@pytest.mark.parametrize('log_field', ['logs', 'events'])
def test_pending_receipt_reused_until_actual_delivery(monkeypatch, log_field):
    monkeypatch.setattr('finn.notification_relay.time.sleep', lambda _: None)
    store, requests = ReceiptStore(), []
    state = {'value': 'ACTIVE'}
    def respond(request):
        requests.append(request)
        assert request.headers['Authorization'] == 'Bearer private-relay-key'
        if request.method == 'POST':
            assert request.url.path == '/v2/publish/https://ntfy.sh'
            assert json.loads(request.content)['topic'] == 'finn_private-topic'
            assert request.headers['Upstash-Retries'] == '1'
            return httpx.Response(200, json={'messageId': 'delivery-1'})
        assert request.url.params['messageId'] == 'delivery-1'
        return httpx.Response(200, json={log_field: [{'messageId': 'other-message', 'state': 'DELIVERED'},
                                                   {'messageId': 'delivery-1', 'state': state['value']}]})
    relay = QStashRelay('https://qstash.upstash.io', 'private-relay-key', store, transport=httpx.MockTransport(respond))
    with pytest.raises(PhoneError, match='still processing'):
        relay('finn_private-topic', ITEM)
    assert json.loads(next(iter(store.values.values())))['delivered'] is False
    state['value'] = 'DELIVERED'
    relay('finn_private-topic', ITEM)
    assert sum(r.method == 'POST' for r in requests) == 1
    count = len(requests)
    relay('finn_private-topic', ITEM)
    assert len(requests) == count


def test_failed_provider_delivery_is_never_accepted(monkeypatch):
    monkeypatch.setattr('finn.notification_relay.time.sleep', lambda _: None)
    store = ReceiptStore()
    def respond(request):
        return httpx.Response(200, json={'messageId': 'failed-1'} if request.method == 'POST' else
                              {'logs': [{'messageId': 'failed-1', 'state': 'FAILED'}]})
    relay = QStashRelay('https://qstash-eu-central-1.upstash.io', 'secret', store, transport=httpx.MockTransport(respond))
    with pytest.raises(PhoneError, match='could not finish'):
        relay('finn_topic', ITEM)
    assert store.values == {}


def test_relay_errors_keep_credentials_out_of_user_message():
    relay = QStashRelay('https://qstash.upstash.io', 'private-key', ReceiptStore(),
                        transport=httpx.MockTransport(lambda _: httpx.Response(401, text='private-key')))
    with pytest.raises(PhoneError) as error:
        relay('finn_private-topic', ITEM)
    assert error.value.status == 503
    assert 'private-key' not in str(error.value) and 'finn_private-topic' not in str(error.value)


@pytest.mark.parametrize('url', ['http://qstash.upstash.io', 'https://evil.example',
                                'https://qstash.upstash.io.evil.example', 'https://u:p@qstash.upstash.io',
                                'https://qstash.upstash.io?key=x', 'https://qstash.upstash.io/v2',
                                'https://qstash.upstash.io:9443'])
def test_relay_rejects_unexpected_hosts(url):
    with pytest.raises(ValueError):
        QStashRelay(url, 'secret', ReceiptStore())
