"""Mobile rendering / evidence-navigation check (Playwright).

Usage: python tests/ui_check.py <dist_dir> <out_dir>
The browser loads the built frontend; every /api/* request is answered by the REAL
framework-free service layer (finn.service.App) over a SYNTHETIC corpus (conftest.py).
This verifies the UI, not real company data and not the FastAPI routing layer."""
from __future__ import annotations

import json
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conftest import FakeNetwork, build_manifest  # noqa: E402
from finn.config import get_settings  # noqa: E402
from finn.contracts import ResearchRequest  # noqa: E402
from finn.db import Store  # noqa: E402
from finn.ingest import ingest_replay  # noqa: E402
from finn.replay import load_manifest  # noqa: E402
from finn.service import App, NotFound  # noqa: E402
from finn.sources.fetch import Fetcher  # noqa: E402

WIDTHS = [360, 390, 430]


def build_app(tmp: Path) -> App:
    mpath = tmp / "manifest.json"
    mpath.write_text(json.dumps(build_manifest()))
    settings = replace(get_settings(), data_dir=tmp / "data", manifest_path=mpath, frontend_dist=tmp / "nodist", openai_api_key=None)
    store = Store(settings.db_path, settings.files_dir)
    fetcher = Fetcher(store, client=httpx.Client(transport=httpx.MockTransport(FakeNetwork())), min_interval_s=0)
    ingest_replay(store, fetcher, settings, load_manifest(mpath), ["TESTCO"], log=lambda s: None)
    return App(settings, store=store, client=None, start_worker=False)


def main(dist: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    app = build_app(Path(tempfile.mkdtemp()))
    state = {"api_down": False, "slow_jobs": False}
    results = []

    def respond(route, status, body, ctype="application/json"):
        route.fulfill(status=status, body=body if isinstance(body, (bytes, str)) else json.dumps(body), content_type=ctype)

    def api_handler(route, request):
        if state["api_down"]:
            return route.abort()
        u = urlparse(request.url)
        parts = u.path.strip("/").split("/")[1:]
        try:
            if parts == ["health"]:
                return respond(route, 200, app.health())
            if parts[0] == "companies" and parts[-1] == "overview":
                return respond(route, 200, app.company_overview(parts[1], parse_qs(u.query).get("mode", ["replay"])[0]))
            if parts == ["research"] and request.method == "POST":
                sub = app.submit_research(ResearchRequest(**json.loads(request.post_data)))
                if not state["slow_jobs"]:
                    app.run_job(sub["job_id"])
                return respond(route, 202, sub)
            if parts[0] == "jobs":
                return respond(route, 200, app.job(parts[1]))
            if parts[0] == "evidence":
                return respond(route, 200, app.evidence(parts[1]))
            if parts[0] == "documents" and parts[-1] == "file":
                return respond(route, 200, app.document_file(parts[1]).read_bytes(), "application/pdf")
        except NotFound as exc:
            return respond(route, 404, {"detail": {"state": exc.state, "message": str(exc)}})
        return respond(route, 404, {"detail": "not found"})

    def static_handler(route, request):
        path = urlparse(request.url).path.lstrip("/") or "index.html"
        f = dist / path
        if not f.is_file():
            f = dist / "index.html"
        ctype = {"js": "text/javascript", "css": "text/css", "html": "text/html"}.get(f.suffix.lstrip("."), "application/octet-stream")
        route.fulfill(status=200, body=f.read_bytes(), content_type=ctype)

    def check(name, cond, detail=""):
        results.append({"check": name, "status": "pass" if cond else "fail", "detail": detail})

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width in WIDTHS:
            ctx = browser.new_context(viewport={"width": width, "height": 800}, device_scale_factor=2, is_mobile=True, has_touch=True)
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("**/api/**", api_handler)
            page.route("http://finn.test/*", static_handler)
            page.route("http://finn.test/assets/*", static_handler)

            def no_overflow(label):
                sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
                check(f"{width}px {label}: no horizontal overflow", sw <= cw, f"scrollWidth={sw} clientWidth={cw}")

            def small_targets():
                return page.evaluate("""() => [...document.querySelectorAll('main button, main a.btn, .sheet button, .sheet a.btn, main input')]
                    .filter(e => e.offsetParent !== null).map(e => [e.textContent.trim().slice(0,30), e.getBoundingClientRect().height])
                    .filter(([t,h]) => h < 43.5)""")

            page.goto("http://finn.test/#/")
            page.wait_for_selector("text=Historical replay")
            banner = page.inner_text(".mode-banner")
            check(f"{width}px banner shows replay mode, filing dates and cutoff",
                  "Historical replay" in banner and "30 Apr 2025, 23:59 IST" in banner and "17 Apr 2025" in banner, banner.replace("\n", " | "))
            no_overflow("home")
            page.screenshot(path=str(out / f"{width}_1_home.png"), full_page=True)

            page.fill("#sym", "testco")
            page.press("#sym", "Enter")
            page.wait_for_selector("text=Testco Industries Limited")
            body = page.inner_text("main")
            check(f"{width}px company: identity, announcements, EOD, excluded docs",
                  "INE000T01011" in body and "Outcome of Board Meeting" in body and "103.50" in body
                  and "published after replay cutoff" in body and "publication availability unverified" in body)
            no_overflow("company")
            st = small_targets()
            check(f"{width}px company: touch targets >= 44px", not st, json.dumps(st))
            page.screenshot(path=str(out / f"{width}_2_company.png"), full_page=True)

            page.click("text=Research this company")
            page.wait_for_selector("text=Retrieved passages (unsummarised")
            body = page.inner_text("main")
            check(f"{width}px research: honest partial state without model",
                  "Research prose not generated" in body and "OPENAI_API_KEY" in body and "Not generated" in body
                  and "Business context" in body and "Management commentary" in body and "Evidence gaps" in body)
            check(f"{width}px research: replay date visible", "historical replay · as of 30 apr 2025" in body.lower(), body[:200])
            no_overflow("research")
            st = small_targets()
            check(f"{width}px research: touch targets >= 44px", not st, json.dumps(st))
            page.screenshot(path=str(out / f"{width}_3_research.png"), full_page=True)

            btn = page.locator(".passage-btn").nth(1)
            btn_text = btn.inner_text()
            btn.click()
            page.wait_for_selector(".sheet >> text=PDF page")
            sheet = page.inner_text(".sheet")
            hrefs = page.eval_on_selector_all(".sheet a", "els => els.map(e => e.getAttribute('href'))")
            pdf_link = next((h for h in hrefs if "/api/documents/" in h), "")
            check(f"{width}px evidence: metadata, passage, cached + original links",
                  "Published" in sheet and "sha256:" in sheet and "Printed page" in sheet and "#page=" in pdf_link
                  and any(h.startswith("https://nsearchives.nseindia.com/") for h in hrefs), json.dumps(hrefs))
            page_in_btn = btn_text.split("PDF p.")[1].split()[0].strip("·") if "PDF p." in btn_text else "?"
            check(f"{width}px evidence: page locator matches citation", f"#page={page_in_btn}" in pdf_link, f"{page_in_btn} vs {pdf_link}")
            no_overflow("evidence sheet")
            st = small_targets()
            check(f"{width}px evidence: touch targets >= 44px", not st, json.dumps(st))
            page.screenshot(path=str(out / f"{width}_4_evidence.png"), full_page=False)
            head = page.evaluate("async (u) => { const r = await fetch(u); const b = new Uint8Array(await r.arrayBuffer()); return String.fromCharCode(...b.slice(0,5)); }", pdf_link.split("#")[0])
            check(f"{width}px evidence: cached PDF endpoint returns PDF bytes", head == "%PDF-", head)
            page.keyboard.press("Escape")
            page.wait_for_selector(".sheet", state="detached")
            focused = page.evaluate("document.activeElement && document.activeElement.className")
            check(f"{width}px evidence: Escape closes and focus returns", focused == "passage-btn", str(focused))

            # unknown ticker vs failure states
            page.goto("http://finn.test/#/c/NOPE")
            page.wait_for_selector("text=Identity could not be resolved")
            check(f"{width}px unknown ticker shows distinct empty state", "not in the NSE equity security master" in page.inner_text("main"))
            page.screenshot(path=str(out / f"{width}_5_unknown.png"), full_page=True)

            state["slow_jobs"] = True
            page.goto("http://finn.test/#/c/TESTCO")
            page.wait_for_selector("text=Research this event")
            page.click("text=Research this event")  # new request key; job held queued to observe progress UI
            page.wait_for_selector("text=Research in progress", timeout=5000)
            check(f"{width}px loading state shows stages and elapsed time", "Resolving company" in page.inner_text("main"))
            page.screenshot(path=str(out / f"{width}_6_loading.png"), full_page=True)
            state["slow_jobs"] = False

            state["api_down"] = True
            page.goto("http://finn.test/#/")
            page.reload()
            page.wait_for_selector("text=FINN server unreachable")
            check(f"{width}px server failure state", "Retry" in page.inner_text("main"))
            page.screenshot(path=str(out / f"{width}_7_failure.png"), full_page=True)
            state["api_down"] = False
            check(f"{width}px no JavaScript errors", not errors, json.dumps(errors))
            ctx.close()
        browser.close()

    (out / "ui_check.json").write_text(json.dumps(results, indent=2))
    failed = [r for r in results if r["status"] != "pass"]
    for r in results:
        print(f"{r['status'].upper():5s} {r['check']}" + (f"  [{r['detail']}]" if r["status"] != "pass" else ""))
    print(f"{len(results) - len(failed)}/{len(results)} UI checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
