"""Application startup + HTTP smoke + restart persistence check against a real server.

Usage (from repo root, venv active): python scripts/smoke.py [--port 8765]
Starts `python -m finn serve`, exercises the HTTP routes with the ingested corpus,
restarts the server and confirms the job record persisted. Writes
data/verification/startup_smoke.json. Requires ingestion to have run first."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("FINN_DATA_DIR", ROOT / "data")) / "verification"


def start(port: int) -> subprocess.Popen:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "finn", "serve", "--port", str(port)], cwd=ROOT / "backend", env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    t0 = time.time()
    while time.time() - t0 < 30:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=2).status_code == 200:
                return proc
        except httpx.HTTPError:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("server did not become healthy within 30s:\n" + (proc.stdout.read() if proc.stdout else ""))


def stop(proc: subprocess.Popen) -> None:
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--symbol", default="INFY")
    args = ap.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    results = []

    def check(name, ok, detail=None):
        results.append({"check": name, "status": "pass" if ok else "fail", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f"  [{detail}]"))

    proc = None
    try:
        t0 = time.time()
        proc = start(args.port)
        check("server starts and /api/health responds", True, {"seconds": round(time.time() - t0, 1)})
        h = httpx.get(f"{base}/api/health").json()
        check("health reports replay manifest", bool(h.get("replay")), h.get("replay"))
        check("health reports model credential state (presence only)", "model_configured" in h, {"model_configured": h.get("model_configured")})
        idx = httpx.get(f"{base}/")
        check("frontend index served from same origin", idx.status_code == 200 and "<div id=\"root\">" in idx.text, idx.status_code)
        deep = httpx.get(f"{base}/c/{args.symbol}")
        check("direct navigation path falls back to SPA index", deep.status_code == 200 and "root" in deep.text, deep.status_code)
        unknown = httpx.get(f"{base}/api/companies/NOTAREALSYMBOL1/overview")
        check("unknown symbol -> 404 unknown_symbol", unknown.status_code == 404 and unknown.json()["detail"]["state"] == "unknown_symbol", unknown.text[:200])
        ov = httpx.get(f"{base}/api/companies/{args.symbol}/overview")
        ovj = ov.json() if ov.status_code == 200 else {}
        check("company overview returns identity, announcements, EOD and documents",
              ov.status_code == 200 and ovj["company"]["symbol"] == args.symbol and ovj["announcements"] and ovj["eod"] and ovj["documents"]["eligible"],
              {"announcements": len(ovj.get("announcements", [])), "eod": len(ovj.get("eod", [])),
               "eligible": len(ovj.get("documents", {}).get("eligible", [])), "excluded": len(ovj.get("documents", {}).get("excluded", []))})
        sub = httpx.post(f"{base}/api/research", json={"symbol": args.symbol, "mode": "replay"})
        check("POST /api/research returns a job id promptly", sub.status_code == 202, sub.text[:200])
        job_id = sub.json()["job_id"]
        job = {}
        for _ in range(120):
            job = httpx.get(f"{base}/api/jobs/{job_id}").json()
            if job["state"] not in ("queued", "running"):
                break
            time.sleep(1)
        check("research job reaches a terminal state", job.get("state") in ("completed", "partial"),
              {"state": job.get("state"), "error": job.get("error"), "generation": (job.get("result") or {}).get("generation")})
        res = job.get("result") or {}
        ids = (res.get("business_context") or {}).get("candidate_evidence_ids", []) + (res.get("management_commentary") or {}).get("candidate_evidence_ids", [])
        if ids:
            ev = httpx.get(f"{base}/api/evidence/{ids[0]}").json()
            check("evidence route returns passage with document provenance",
                  ev["document"]["content_hash"] and ev["document"]["published_at"] and ev["passage"]["page_index"] >= 1,
                  {"doc": ev["document"]["doc_type"], "page": ev["passage"]["page_index"]})
            f = httpx.get(f"{base}/api/documents/{ev['document']['version_id']}/file")
            check("cached PDF route serves the original bytes", f.status_code == 200 and f.content[:5] == b"%PDF-",
                  {"bytes": len(f.content)})
        else:
            check("research retrieved evidence passages", False, "no candidate evidence ids")
        stop(proc)
        proc = start(args.port)
        again = httpx.get(f"{base}/api/jobs/{job_id}").json()
        check("job record survives a server restart", again.get("state") == job.get("state"), {"before": job.get("state"), "after": again.get("state")})
    except Exception as exc:  # noqa: BLE001
        check("smoke run completed without exceptions", False, f"{exc.__class__.__name__}: {exc}")
    finally:
        if proc:
            stop(proc)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "startup_smoke.json").write_text(json.dumps(results, indent=2, default=str))
    failed = [r for r in results if r["status"] != "pass"]
    print(f"{len(results) - len(failed)}/{len(results)} smoke checks passed -> {OUT / 'startup_smoke.json'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
