"""Per-device, opt-in filing alerts backed by durable Redis storage.

Only public NSE subjects and source links leave FINN. Management credentials and
notification topics stay outside public feeds, URLs, exports and the corpus DB.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from . import alerts

GROUPS = {
    "results": {"label": "Results", "description": "Quarterly and annual financial results", "categories": ["results"]},
    "business": {"label": "Major business changes", "description": "Acquisitions, management, fundraising, legal matters, ratings and capex", "categories": ["M&A", "management_change", "fund_raise", "litigation", "credit_rating", "capex", "pledging"]},
    "shareholders": {"label": "Dividends and share changes", "description": "Dividends, bonus issues and stock splits", "categories": ["dividend", "bonus_split"]},
    "calls": {"label": "Earnings calls", "description": "Call announcements and transcripts", "categories": ["earnings_call"]},
}
MAX_SUBSCRIPTIONS = 200
DAILY_BUDGET = 200  # Shared ntfy.sh allowance leaves headroom below its 250/day limit.
MAX_DAILY_PER_DEVICE = 3
PREFIX = "finn:phone:v1:"


class PhoneError(Exception):
    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.status = status


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RedisPhoneStore:
    def __init__(self, url: str, token: str, *, transport=None):
        parsed = urlparse(url)
        if (parsed.scheme != "https" or not (parsed.hostname or "").endswith(".upstash.io")
                or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise ValueError("Use the HTTPS REST URL from your Upstash Redis console.")
        self.url, self.token, self.transport = url.rstrip("/"), token, transport

    def command(self, *command):
        try:
            with httpx.Client(timeout=12, transport=self.transport, follow_redirects=False) as client:
                response = client.post(self.url, headers={"Authorization": f"Bearer {self.token}"}, json=list(command))
            response.raise_for_status()
            value = response.json()
            if "error" in value or "result" not in value:
                raise ValueError("invalid Redis response")
            return value["result"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise PhoneError("Phone alert storage is temporarily unavailable. Your saved settings have been kept.") from exc

    def get(self, identity: str):
        value = self.command("HGET", PREFIX + "subscriptions", identity)
        return json.loads(value) if value is not None else None

    def save(self, identity: str, record: dict):
        script = """
        if redis.call('HEXISTS', KEYS[1], ARGV[1]) == 0 and redis.call('HLEN', KEYS[1]) >= tonumber(ARGV[3]) then return 0 end
        redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
        if ARGV[4] == 'queued' then redis.call('HSET', KEYS[2], ARGV[1], '1') else redis.call('HDEL', KEYS[2], ARGV[1]) end
        return 1
        """
        if not self.command("EVAL", script, 2, PREFIX + "subscriptions", PREFIX + "test-queue", identity,
                            json.dumps(record), MAX_SUBSCRIPTIONS, record.get("test_state") or ""):
            raise PhoneError("The free alert service is full. Please try again later.", 503)

    def all(self):
        rows = self.command("HGETALL", PREFIX + "subscriptions") or []
        return {rows[i]: json.loads(rows[i + 1]) for i in range(0, len(rows), 2)}

    def delete(self, identity: str):
        self.command("EVAL", "redis.call('HDEL', KEYS[1], ARGV[1]); return redis.call('HDEL', KEYS[2], ARGV[1])",
                     2, PREFIX + "subscriptions", PREFIX + "test-queue", identity)

    def pending_tests(self):
        return self.command("HKEYS", PREFIX + "test-queue") or []

    @contextmanager
    def lock(self, name: str, seconds: int = 90):
        key, owner = PREFIX + "lock:" + name, secrets.token_hex(16)
        if not self.command("SET", key, owner, "NX", "EX", seconds):
            raise PhoneError("An alert operation is already running. Try again shortly.", 409)
        try:
            yield
        finally:
            self.command("EVAL", "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0", 1, key, owner)

    def allowance(self, name: str, limit: int, seconds: int) -> bool:
        script = """
        local count = tonumber(redis.call('GET', KEYS[1]) or '0')
        if count >= tonumber(ARGV[1]) then return 0 end
        local next_count = redis.call('INCR', KEYS[1])
        if next_count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end
        return 1
        """
        return bool(self.command("EVAL", script, 1, PREFIX + "limit:" + name, limit, seconds))

    def status(self):
        value = self.command("GET", PREFIX + "status")
        return json.loads(value) if value else None

    def save_status(self, value: dict):
        self.command("SET", PREFIX + "status", json.dumps(value))

    def delivery_status(self):
        value = self.command("GET", PREFIX + "delivery-status")
        return json.loads(value) if value else None

    def save_delivery_status(self, value: dict):
        self.command("SET", PREFIX + "delivery-status", json.dumps(value))


class PhoneAlerts:
    def __init__(self, store: RedisPhoneStore | None, companies: list[dict], *, sender=None):
        self.store = store
        self.companies = companies
        self.symbols = {row["symbol"] for row in companies}
        self.sender = sender or alerts._send_ntfy

    def require_store(self):
        if self.store is None:
            raise PhoneError("Phone alerts are awaiting the service owner's storage setup. You can still browse company filings.")
        return self.store

    @staticmethod
    def identity(token: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise PhoneError("Open alerts in the browser where you set them up, or restore your saved access code.", 401)
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def public(record: dict) -> dict:
        return {key: record.get(key) for key in ("symbols", "groups", "active", "topic", "created_at", "updated_at", "enabled_at", "test_requested_at", "test_accepted_at", "test_state", "test_error", "last_delivery_at", "last_items")}

    def get(self, token: str):
        record = self.require_store().get(self.identity(token))
        if record is None:
            raise PhoneError("This browser has no saved phone subscription yet.", 404)
        return self.public(record)

    def save(self, token: str, symbols: list[str], groups: list[str], active: bool, client: str):
        store, identity = self.require_store(), self.identity(token)
        symbols, groups = sorted(set(symbols)), sorted(set(groups))
        if not symbols or not set(symbols) <= self.symbols:
            raise PhoneError("Choose at least one company from FINN's covered companies.", 422)
        if not groups or not set(groups) <= GROUPS.keys():
            raise PhoneError("Choose at least one available filing type.", 422)
        with store.lock(identity):
            record = store.get(identity)
            now = timestamp()
            if record is None:
                ip_hash = hashlib.sha256(client.encode()).hexdigest()
                if not store.allowance("signup:" + ip_hash, 10, 3600):
                    raise PhoneError("Too many new setups from this connection. Try again in an hour.", 429)
                record = {"topic": "finn_" + secrets.token_hex(24), "created_at": now, "active": False,
                          "symbols": [], "groups": [], "starts": {}, "group_starts": {}, "sent": {}, "last_items": []}
            if active and not record.get("test_accepted_at"):
                raise PhoneError("Send a test and confirm it arrived before enabling filing alerts.", 409)
            if active and not record.get("enabled_at"):
                record["enabled_at"] = now
            restarting = active and not record["active"]
            starts = {s: now if restarting else record["starts"].get(s, now) for s in symbols}
            group_starts = {g: now if restarting else record["group_starts"].get(g, now) for g in groups}
            record.update(symbols=symbols, groups=groups, active=active, starts=starts, group_starts=group_starts, updated_at=now)
            store.save(identity, record)
            return self.public(record)

    def delete(self, token: str):
        store, identity = self.require_store(), self.identity(token)
        with store.lock(identity):
            store.delete(identity)
        return {"deleted": True}

    def test(self, token: str):
        """Queue one test for the delivery worker."""
        store, identity = self.require_store(), self.identity(token)
        with store.lock(identity):
            record = store.get(identity)
            if record is None:
                raise PhoneError("Save your company choices first.", 404)
            if record.get("test_state") == "queued":
                store.save(identity, record)
                return {"accepted": False, "queued": True}
            if not store.allowance("test:" + identity, 1, 60):
                raise PhoneError("Wait a minute before sending another test.", 429)
            today = datetime.now(timezone.utc).date().isoformat()
            if not store.allowance("test-day:" + identity + ":" + today, 5, 172800):
                raise PhoneError("This setup has used its five free tests today. Try again tomorrow.", 429)
            record.update(test_requested_at=timestamp(), test_state="queued", test_error=None)
            store.save(identity, record)
            return {"accepted": False, "queued": True}

    def deliver_tests(self, *, dry_run=False):
        """Send queued tests through the configured delivery transport."""
        store = self.require_store()
        result = {"queued": 0, "sent": 0, "failed": 0}
        with store.lock("test-dispatch", 600):
            deadline = time.monotonic() + 150
            for identity in store.pending_tests():
                if time.monotonic() >= deadline:
                    break
                with store.lock(identity):
                    record = store.get(identity)
                    if record is None or record.get("test_state") != "queued":
                        if record is None:
                            store.delete(identity)
                        else:
                            store.save(identity, record)
                        continue
                    result["queued"] += 1
                    if dry_run:
                        continue
                    today = datetime.now(timezone.utc).date().isoformat()
                    if not store.allowance("delivery:" + today, DAILY_BUDGET, 172800):
                        record["test_error"] = "Today's free notification allowance is full. Your test remains queued."
                        store.save(identity, record)
                        break
                    item = {"title": "FINN · Your phone test",
                            "key": "phone-test:" + record["test_requested_at"],
                            "body": "Your FINN phone setup test. Your selected companies: " + ", ".join(record["symbols"]) + ". Tap to open Portfolio Review.",
                            "company_url": alerts.DEFAULT_SITE_URL}
                    try:
                        self.sender(record["topic"], item)
                    except (httpx.HTTPError, OSError, PhoneError) as exc:
                        provider_status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                        logging.getLogger(__name__).warning("Phone test delivery failed (%s, HTTP %s)", type(exc).__name__, provider_status)
                        record["test_error"] = "The free delivery service is busy. Your test remains queued for the next check."
                        store.save(identity, record)
                        result["failed"] += 1
                        if provider_status == 429:
                            break
                        continue
                    record.update(test_accepted_at=timestamp(), test_state="accepted", test_error=None)
                    store.save(identity, record)
                    result["sent"] += 1
        return result

    def check(self, refresh, portfolio, *, dry_run=False, scheduled=True):
        """Shared scheduler entry point. A timer receipt is separate from a source check."""
        store = self.require_store()
        with store.lock("delivery-check", 850):
            tests = self.deliver_tests(dry_run=dry_run)
            last = store.status()
            recent = last and (datetime.now(timezone.utc) - datetime.fromisoformat(last['checked_at'])).total_seconds() < 29 * 60
            if scheduled and (recent or (not dry_run and not store.allowance('filing-check-interval', 1, 29 * 60))):
                filings = {"skipped": "The next filing check is not due yet."}
            else:
                filings = self.dispatch(refresh, portfolio, dry_run=dry_run)
            result = {"checked_at": timestamp(), "dry_run": dry_run, "tests": tests, "filings": filings}
            if not dry_run:
                store.save_delivery_status(result)
            return result

    def dispatch(self, refresh, portfolio, *, dry_run=True):
        store = self.require_store()
        with store.lock("dispatch", 900):
            deadline = time.monotonic() + 480
            subscriptions = store.all()
            if not any(row["active"] for row in subscriptions.values()):
                return {"dry_run": dry_run, "active": 0, "sent": 0, "failed": 0, "note": "No active subscribers."}
            report = refresh()
            checked = {row["symbol"] for row in report.get("companies", []) if row.get("state") == "fetched"}
            categories = [c for group in GROUPS.values() for c in group["categories"]]
            candidates = alerts.build_notifications(portfolio(), {}, checked_symbols=checked, extra_categories=categories,
                                                    now=datetime.now(timezone.utc), days=7)
            status = {"checked_at": timestamp(), "holdings_checked": len(checked), "holdings_total": len(self.symbols),
                      "unchecked_symbols": sorted(self.symbols - checked),
                      "dry_run": dry_run, "sent": 0, "failed": 0, "matched_devices": 0, "deferred": 0}
            eligible = [identity for identity, record in subscriptions.items() if record["active"] and self._matching(record, candidates)]
            order = sorted(eligible, key=lambda identity: (subscriptions[identity].get("last_delivery_at") or "", identity))
            for position, identity in enumerate(order):
                if time.monotonic() >= deadline:
                    status["deferred"] += len(order) - position
                    break
                try:
                    with store.lock(identity):
                        record = store.get(identity)
                        if record is None or not record["active"]:
                            continue
                        pending = self._matching(record, candidates)
                        if not pending:
                            continue
                        status["matched_devices"] += 1
                        if dry_run:
                            continue
                        today = datetime.now(timezone.utc).date().isoformat()
                        daily = record.get("daily", {"date": today, "count": 0})
                        if daily["date"] != today:
                            daily = {"date": today, "count": 0}
                        if daily["count"] >= MAX_DAILY_PER_DEVICE:
                            status["deferred"] += 1
                            continue
                        if not store.allowance("delivery:" + today, DAILY_BUDGET, 172800):
                            status["deferred"] += len(order) - position
                            break
                        batch = pending[:5]
                        message = self._message(batch)
                        while len(message["body"].encode("utf-8")) > 4000:
                            batch.pop()
                            message = self._message(batch)
                        self.sender(record["topic"], message)
                        now = timestamp()
                        sent = dict(record.get("sent", {}))
                        cutoff = datetime.now(timezone.utc) - timedelta(days=8)
                        sent = {key: published for key, published in sent.items() if datetime.fromisoformat(published) >= cutoff}
                        for item in batch:
                            sent[item.get("dedupe_key") or item["key"]] = item["published_at"]
                        record.update(sent=dict(sorted(sent.items(), key=lambda row: row[1])[-1000:]),
                                      last_delivery_at=now, last_items=[self._receipt(item) for item in batch],
                                      daily={"date": today, "count": daily["count"] + 1})
                        store.save(identity, record)
                        status["sent"] += 1
                except (PhoneError, httpx.HTTPError):
                    status["failed"] += 1
            if not dry_run:
                store.save_status(status)
            return status

    @staticmethod
    def _matching(record, candidates):
        selected = {category: group for group in record["groups"] for category in GROUPS[group]["categories"]}
        matches = []
        seen = set(record.get("sent", {}))
        for item in sorted(candidates, key=lambda row: datetime.fromisoformat(row["published_at"]), reverse=True):
            group = selected.get(item["category"])
            symbol = item["symbol"]
            key = item.get("dedupe_key") or item["key"]
            if group is None or symbol not in record["symbols"] or key in seen:
                continue
            published = datetime.fromisoformat(item["published_at"])
            starts = [record["starts"][symbol], record["group_starts"][group]]
            if any(published < datetime.fromisoformat(start) for start in starts):
                continue
            matches.append(item)
            seen.add(key)
        return matches

    @staticmethod
    def _receipt(item):
        return {key: item.get(key) for key in ("symbol", "category", "published_at", "filing_url", "company_url", "title", "body")}

    @staticmethod
    def _message(items):
        if len(items) == 1:
            item = items[0]
            if len(item["body"].encode("utf-8")) <= 4000:
                return item
            body = "\n".join([item["body"].split("\n", 1)[0], alerts._published(item["published_at"]),
                              "Tap to open the source. Company: " + item["company_url"], alerts.ADVICE_FOOTER])
            return {**item, "body": body}
        lines = []
        for item in items:
            subject = item["body"].split("\n", 1)[0]
            lines.append(f"{item['title']}\n{subject}\n{alerts._published(item['published_at'])}\n{item['filing_url'] or item['company_url']}")
        return {"title": f"FINN · {len(items)} new filings",
                "body": "\n\n".join(lines) + "\n\nTap opens the first filing. Other sources are linked above.\n" + alerts.ADVICE_FOOTER,
                "company_url": items[0]["company_url"], "click_url": items[0]["filing_url"] or items[0]["company_url"]}
