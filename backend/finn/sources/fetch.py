"""Guarded HTTP retrieval that records every attempt and stores validated bytes by hash.

Source content is treated as untrusted data. Only public HTTPS destinations are fetched;
each redirect hop is re-validated; size is bounded; bytes are checked against the
expected type (an HTML error page served with HTTP 200 is not a PDF).
"""
from __future__ import annotations

import ipaddress
import json
import time
from dataclasses import dataclass
from typing import Literal, Optional
from urllib.parse import urljoin, urlparse

import httpx

from ..db import Store, new_id, utcnow

Expect = Literal["pdf", "csv", "json", "html"]
SUFFIX = {"pdf": ".pdf", "csv": ".csv", "json": ".json", "html": ".html"}
MEDIA = {"pdf": "application/pdf", "csv": "text/csv", "json": "application/json", "html": "text/html"}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class FetchResult:
    attempt_id: str
    url: str
    final_url: Optional[str]
    state: str
    http_status: Optional[int]
    content: Optional[bytes]
    content_hash: Optional[str]
    content_type: Optional[str]
    error: Optional[str]
    retrieved_at: str

    @property
    def ok(self) -> bool:
        return self.state == "fetched"

    def json(self):
        return json.loads(self.content.decode("utf-8")) if self.content else None


class UnsafeURL(ValueError):
    pass


def validate_public_https(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise UnsafeURL(f"only https URLs are fetched (got {parsed.scheme or 'none'})")
    host = (parsed.hostname or "").lower()
    if not host or host == "localhost" or host.endswith(".local") or "." not in host:
        raise UnsafeURL(f"non-public host: {host!r}")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        raise UnsafeURL(f"non-public address: {host}")


def validate_bytes(data: bytes, expect: Expect) -> Optional[str]:
    """Return None when bytes look like the expected type, otherwise a reason."""
    head = data[:1024].lstrip()
    looks_html = head[:15].lower().startswith((b"<!doctype html", b"<html")) or b"<html" in head[:200].lower()
    if expect == "pdf":
        if not data.startswith(b"%PDF-"):
            return "bytes do not start with %PDF- signature" + (" (HTML page received)" if looks_html else "")
        return None
    if looks_html and expect != "html":
        return "HTML page received instead of data"
    if expect == "json":
        try:
            json.loads(data.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            return f"invalid JSON: {exc.__class__.__name__}"
    if expect == "csv":
        try:
            first = data.decode("utf-8", errors="strict").splitlines()[0]
        except Exception:  # noqa: BLE001
            return "CSV is not UTF-8 text"
        if "," not in first:
            return "CSV header row has no comma separators"
    return None


class Fetcher:
    def __init__(
        self,
        store: Store,
        max_bytes: int = 50 * 1024 * 1024,
        client: Optional[httpx.Client] = None,
        min_interval_s: float = 0.5,
    ):
        self.store = store
        self.max_bytes = max_bytes
        self.client = client or httpx.Client(
            headers=BROWSER_HEADERS,
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=False,
        )
        self.min_interval_s = min_interval_s
        self._last_request = 0.0
        self._nse_session_ready = False

    def close(self) -> None:
        self.client.close()

    def _pace(self) -> None:
        wait = self.min_interval_s - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def ensure_nse_session(self) -> FetchResult:
        """NSE's website API expects cookies set by a normal page visit."""
        result = self.get("https://www.nseindia.com/", source_kind="nse_session", expect="html", store_body=False)
        self._nse_session_ready = result.ok
        return result

    def get(
        self,
        url: str,
        *,
        source_kind: str,
        expect: Expect,
        company_id: Optional[str] = None,
        headers: Optional[dict] = None,
        store_body: bool = True,
        retries: int = 1,
    ) -> FetchResult:
        attempt_id = new_id("att")
        started = utcnow()
        state, status, final_url, data, ctype, error = "error", None, None, None, None, None
        for attempt in range(retries + 1):
            state, status, final_url, data, ctype, error = self._get_once(url, expect, headers)
            transient = state == "timeout" or (state == "error" and (status or 0) >= 500)
            if not transient or attempt == retries:
                break
            time.sleep(2.0)
        digest = None
        if state == "fetched" and data is not None and store_body:
            digest = self.store.put_file(data, MEDIA[expect], SUFFIX[expect])
        retrieved_at = utcnow()
        self.store.insert(
            "fetch_attempts",
            {
                "attempt_id": attempt_id,
                "source_kind": source_kind,
                "url": url,
                "final_url": final_url,
                "state": state,
                "http_status": status,
                "content_type": ctype,
                "bytes": len(data) if data is not None else None,
                "content_hash": digest,
                "error": error,
                "company_id": company_id,
                "started_at": started,
                "finished_at": retrieved_at,
            },
        )
        return FetchResult(attempt_id, url, final_url, state, status, data if state == "fetched" else None,
                           digest, ctype, error, retrieved_at)

    def _get_once(self, url: str, expect: Expect, headers: Optional[dict]):
        current = url
        try:
            for _hop in range(6):
                validate_public_https(current)
                self._pace()
                with self.client.stream("GET", current, headers=headers or {}) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location")
                        if not location:
                            return "error", resp.status_code, current, None, None, "redirect without location"
                        current = urljoin(current, location)
                        continue
                    ctype = resp.headers.get("content-type")
                    if resp.status_code in (401, 403):
                        return "blocked", resp.status_code, current, None, ctype, f"HTTP {resp.status_code}"
                    if resp.status_code == 404:
                        return "not_found", 404, current, None, ctype, "HTTP 404"
                    if resp.status_code != 200:
                        return "error", resp.status_code, current, None, ctype, f"HTTP {resp.status_code}"
                    declared = resp.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > self.max_bytes:
                        return "invalid_document", 200, current, None, ctype, f"declared size {declared} exceeds limit"
                    buf = bytearray()
                    for chunk in resp.iter_bytes():
                        buf.extend(chunk)
                        if len(buf) > self.max_bytes:
                            return "invalid_document", 200, current, None, ctype, "size limit exceeded"
                    data = bytes(buf)
                    problem = validate_bytes(data, expect)
                    if problem:
                        return "invalid_document", 200, current, None, ctype, problem
                    return "fetched", 200, current, data, ctype, None
            return "error", None, current, None, None, "too many redirects"
        except UnsafeURL as exc:
            return "error", None, current, None, None, f"unsafe URL: {exc}"
        except httpx.TimeoutException:
            return "timeout", None, current, None, None, "timeout"
        except httpx.HTTPError as exc:
            return "error", None, current, None, None, f"{exc.__class__.__name__}: {str(exc)[:200]}"
