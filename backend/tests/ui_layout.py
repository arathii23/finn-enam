"""Reproducible FINN mobile layout and filing-link smoke test.

Serve the built candidates locally and pass their URLs. Install Playwright in a
test environment and pass --chrome to use an installed Chromium executable.
This browser rehearsal never counts as a physical-phone T1 measurement.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

WIDTHS = (360, 390, 430)


def audit(browser, base, mode, width):
    context = browser.new_context(viewport={"width": width, "height": 850},
                                  device_scale_factor=1, is_mobile=True, has_touch=True)
    start = perf_counter()
    page = context.new_page()
    captured = []
    page.on("pageerror", lambda error: captured.append(str(error)))

    def serve_only_local(route):
        destination = urlsplit(route.request.url)
        if destination.netloc == urlsplit(base).netloc:
            route.continue_()
        else:
            route.abort()

    context.route("**/*", serve_only_local)
    page.goto(base + "#/")
    expect(page.get_by_role("heading", name="Since your last visit")).to_be_visible()
    expect(page.get_by_text("Manual digest", exact=False)).to_be_visible()
    expect(page.get_by_role("link", name="Historical replay")).to_be_visible()
    first = page.locator(".digest-card").first
    primary = first.get_by_role("link", name="Open filing ↗")
    expect(primary).to_be_visible()
    link = primary.get_attribute("href")
    assert link and urlsplit(link).scheme == "https" and "nseindia" in urlsplit(link).hostname
    box = primary.bounding_box()
    assert box and box["height"] >= 43.9, f"Filing link too short: {box}"
    assert box["y"] + box["height"] <= 700, f"First filing link below 700px: {box}"
    intro_ms = round((perf_counter() - start) * 1000, 1)

    def no_overflow():
        dimensions = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        assert dimensions[0] <= dimensions[1], f"Horizontal overflow {dimensions} on {page.url}"

    no_overflow()
    expect(page.get_by_role("navigation", name="Primary").get_by_text("Trust", exact=True)).to_have_count(0)
    page.get_by_text("Sources and checks", exact=True).click()
    expect(page.get_by_role("link", name="Source coverage and quality")).to_be_visible()
    page.get_by_text("Sources and checks", exact=True).click()

    first.get_by_role("button", name="Seen", exact=True).click()
    expect(first).to_have_class("digest-card digest-seen")
    page.get_by_role("button", name="Mark all as seen", exact=False).click()
    expect(page.get_by_text("No unseen filings in these stored records.")).to_be_visible()
    watermark = page.evaluate("JSON.parse(localStorage.getItem('finn.lastVisit.v1')).watermark")
    assert watermark
    page.reload()
    expect(page.get_by_text("No unseen filings in these stored records.")).to_be_visible()
    assert page.evaluate("JSON.parse(localStorage.getItem('finn.lastVisit.v1')).watermark") == watermark
    no_overflow()

    digest_url = base + "digest.json" if mode == "static" else base + "api/digest"
    fixture = context.request.get(digest_url).json()
    revision = next(item for item in fixture["items"] if item["tier"] == 1)
    revision["version"] = "feedfeedfeedfeed"
    revision["updated"] = True
    before = (datetime.now(timezone.utc) - timedelta(hours=26, minutes=5)).isoformat()
    fixture["checks"]["last_full_check_at"] = before
    for row in fixture["checks"]["holdings"]:
        if row["symbol"] in {"LT", "SUNPHARMA", "ICICIBANK"}:
            row.update(state="timeout" if row["symbol"] == "LT" else "error", checked_at=None, announcements=0)
    fixture["checks"]["holdings_checked"] = 12
    page.route(digest_url, lambda route: route.fulfill(json=fixture))
    page.reload()
    expect(page.get_by_text("Updated filing details", exact=True)).to_be_visible()
    expect(page.get_by_text("12/15 holdings", exact=False)).to_be_visible()
    expect(page.get_by_text("Last full check 26 h ago", exact=False)).to_be_visible()
    for holding in ("LT", "SUNPHARMA", "ICICIBANK"):
        expect(page.locator(".freshness-gaps").get_by_text(holding, exact=True)).to_be_visible()
    assert page.evaluate("JSON.parse(localStorage.getItem('finn.lastVisit.v1')).watermark") == watermark
    page.unroute(digest_url)

    page.goto(base + "#/c/CERA?" + ("results=latest" if mode == "static" else "mode=live"))
    card = page.get_by_role("heading", name="Results scorecard")
    expect(card).to_be_visible()
    expect(page.get_by_role("button", name=re.compile(r"Standalone · Sept? 2026"))).to_have_attribute("aria-pressed", "true")
    expect(page.get_by_text("No verified consolidated filing for the quarter ended 2026-09-30", exact=False)).to_be_visible()
    no_overflow()

    page.goto(base + "#/c/ULTRACEMCO?mode=replay")
    pdf_chip = page.get_by_text("Differs from PDF", exact=True)
    expect(pdf_chip).to_be_visible()
    pdf_chip.click()
    difference = page.locator(".financial-discrepancy")
    expect(difference.get_by_text("PDF currency is unidentified.", exact=False)).to_be_visible()
    pdf_url = difference.get_by_role("link", name="Open PDF", exact=False).get_attribute("href")
    assert pdf_url and "#page=" in pdf_url
    assert difference.get_by_role("link", name="Open XBRL", exact=True).get_attribute("href")
    no_overflow()

    page.goto(base + "#/trust")
    expect(page.get_by_role("heading", name="Source coverage and quality")).to_be_visible()
    expect(page.locator(".trust-holdings > li")).to_have_count(15)
    no_overflow()
    if mode == "static":
        page.goto(base + "#/c/HDFCBANK?mode=replay")
        expect(page.get_by_text("Quarter ended 2025-03-31", exact=False).first).to_be_visible()
        page.goto(base + "#/c/INFY?mode=replay")
        page.get_by_text("Inspect eligible and excluded documents", exact=True).click()
        expect(page.get_by_text("published after replay cutoff", exact=False).first).to_be_visible()
        page.goto(base + "#/c/ZZZQX")
        expect(page.get_by_text("Not in this snapshot", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Open live app", exact=False)).to_be_visible()
        page.evaluate("localStorage.removeItem('finn.digest.v1')")
        page.route("**/digest.json", lambda route: route.fulfill(status=404, body="missing"))
        page.goto(base + "#/")
        expect(page.get_by_text("Current digest unavailable. Showing the historical replay.", exact=True)).to_be_visible()
        expect(page.get_by_text("What needs your attention", exact=True)).to_be_visible()
        page.get_by_role("button", name="Full replay").click()
        expect(page.get_by_text("17 Apr 2025 – 30 Apr 2025", exact=False).first).to_be_visible()
        no_overflow()
    assert not captured, captured
    context.close()
    return {"mode": mode, "width": width, "result": "pass", "digest_first_link_visible_ms": intro_ms,
            "checks": ["digest", "source link above 700px", "44px target", "seen and reload",
                       "partial coverage", "26 h check age", "revision returns", "watermark stays",
                       "automatic basis", "PDF and XBRL links", "trust coverage", "no overflow"] +
                      (["snapshot miss", "replay fallback", "replay cutoff examples"] if mode == "static" else [])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static", required=True)
    parser.add_argument("--live", required=True)
    parser.add_argument("--chrome")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chrome, headless=True)
        for mode, url in (("static", args.static), ("live", args.live)):
            for width in WIDTHS:
                try:
                    results.append(audit(browser, url, mode, width))
                except Exception as exc:
                    results.append({"mode": mode, "width": width, "result": "fail", "error": str(exc).split("\nAria snapshot:")[0]})
        version = browser.version
        browser.close()
    report = {"recorded_at": datetime.now(timezone.utc).isoformat(), "browser": version,
              "scope": "Local Chromium mobile viewport rehearsal. No physical-phone or PDF viewer timing.",
              "results": results, "passed": sum(row["result"] == "pass" for row in results)}
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['passed']}/{len(results)} layouts passed")
    return 0 if report["passed"] == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
