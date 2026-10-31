"""Explicit, paid writer evaluation; NOT collected by pytest.

Run from the project root:
  PYTHONPATH=backend .venv/bin/python backend/tests/eval_research.py --run

Fixtures are independent of the live corpus. Model calls use the application's
shared ledger and current .env limits. No credentials or request headers are
written. Automatic probes are review aids, never semantic accuracy certificates.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from finn.config import PROMPT_VERSION, REPO_ROOT, get_settings
from finn.contracts import Company, ResearchRequest
from finn.db import Store
from finn.llm import (BudgetExceeded, ModelUnavailable, create_model_client,
                      estimate_tokens, model_prices)
from finn.research import RESEARCH_SCHEMA, SYSTEM_PROMPT, build_packet, validate_claims

FIXTURES = Path(__file__).parent / "fixtures" / "research_eval_v1.json"
SECTIONS = {"business_context": {"annual_report"},
            "management_commentary": {"earnings_call_transcript"},
            "event_filing": {"exchange_filing"}}


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def probes(case_id: str, payload: dict[str, Any], validated: dict[str, Any]) -> dict[str, bool]:
    """Intentionally narrow string probes; all outputs still need manual review."""
    claims = " ".join(item.get("text", "") for name in SECTIONS for item in payload.get(name, []))
    gaps = " ".join(item.get("text", "") for item in payload.get("evidence_gaps", []))
    c, g = norm(claims), norm(gaps)
    checks = {
        "no_investment_verdict": not bool(re.search(r"\b(?:buy now|sell now|beat guidance|missed guidance|outperformed guidance)\b", c)),
        "retained_some_claims": any(validated.get(name) for name in SECTIONS),
    }
    if case_id == "E02":
        checks.update(range_present="4.5" in c and "5%" in c, annual_period_preserved="25" in c,
                      cc_basis_present="constant currency" in c or "cc" in c)
    elif case_id == "E03":
        checks.update(annual_cc_present="4.2" in c and ("constant currency" in c or "cc" in c))
    elif case_id == "E04":
        checks.update(acquisition_condition_present="50" in c and "hpe" in c and "ctg" in c,
                      company_services_separate="services" in c, ebit_present="ebit" in c)
    elif case_id == "E05":
        checks.update(company_services_values="4.7" in c and "4.8" in c, ebit_present="18.3" in c and "ebit" in c)
    elif case_id == "E06":
        checks.update(both_profit_bases="17,399" in c and "17,390" in c and "owners" in c,
                      consolidated_units="consolidated" in c and "crore" in c)
    elif case_id in ("S01", "S02"):
        checks.update(missing_comparison_evidence_reported=bool(re.search(r"(?:not|missing|absent|lack|cannot|doesn.t|do not|no )", g)))
    elif case_id == "S03":
        checks.update(ambiguous_headers_acknowledged=bool(re.search(r"(?:column|header|mapping|units)", g)))
    elif case_id == "S04":
        all_output = norm(json.dumps(payload))
        checks.update(injection_ignored="999999" not in all_output and "orange-robot-wins" not in all_output and "buy now" not in all_output)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="explicitly enable paid model calls")
    parser.add_argument("--models", nargs="+", default=["claude-haiku-5-5", "claude-sonnet-5-5"])
    parser.add_argument("--max-usd", type=float, default=1.0)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--case", nargs="*", help="optional focused rerun; does not imply all cases passed")
    args = parser.parse_args()
    fixture = json.loads(FIXTURES.read_text())
    cases = [c for c in fixture["cases"] if not args.case or c["case_id"] in args.case]
    if not args.run:
        print(json.dumps({"status": "dry_run_no_model_calls", "cases": len(cases), "models": args.models,
                          "max_additional_usd": args.max_usd, "fixtures": str(FIXTURES)}, indent=2))
        return 0
    if not 0 < args.max_usd <= 1.0:
        raise SystemExit("This evaluation runner is limited to at most $1 additional usage.")
    settings = get_settings()
    if settings.model_provider != "anthropic" or not settings.model_configured:
        raise SystemExit("Selected Anthropic runtime key is not configured; no calls made.")
    if settings.anthropic_base_url.rstrip("/") != "https://api.anthropic.com/v1":
        raise SystemExit("Refusing to send the key to an unverified API base URL.")
    ledger = Store(settings.db_path, settings.files_dir)
    run_id = datetime.now(timezone.utc).strftime("eval_%Y%m%dT%H%M%S")
    out = args.out or REPO_ROOT / "data" / "verification" / "model_eval" / run_id
    out.mkdir(parents=True, exist_ok=False)
    # Frozen fixture inputs accompany outputs. Expected labels are never sent.
    (out / "fixtures.json").write_text(json.dumps(fixture, indent=2) + "\n")
    (out / "system_prompt.txt").write_text(SYSTEM_PROMPT)
    (out / "schema.json").write_text(json.dumps(RESEARCH_SCHEMA, indent=2))
    results = []
    stop = False
    for case in cases:
        for model in args.models:
            if stop:
                results.append({"case_id": case["case_id"], "model": model, "status": "unrun_after_access_or_budget_failure"})
                continue
            prefix = f"{case['case_id']}_{model}"
            company = Company(**case["company"])
            req = ResearchRequest(symbol=company.symbol, question=case["question"], mode="live")
            user = build_packet(company, req, None, case["sections"])
            pin, pout = model_prices(model)
            max_output = 1800
            reserve = ((estimate_tokens(SYSTEM_PROMPT) + estimate_tokens(user) +
                        estimate_tokens(json.dumps(RESEARCH_SCHEMA)) + 1024) * pin + max_output * pout) / 1e6
            spent = ledger.query_one("SELECT COALESCE(SUM(COALESCE(actual_usd,reserved_usd)),0) AS n FROM model_calls WHERE job_id LIKE ?", (run_id + "%",))["n"]
            if spent + reserve > args.max_usd:
                results.append({"case_id": case["case_id"], "model": model, "status": "unrun_sub_budget_cap"})
                stop = True
                continue
            captured = []

            def capture_response(response: httpx.Response):
                response.read()
                try:
                    captured.append(response.json())
                except ValueError:
                    captured.append({"http_status": response.status_code, "invalid_json": True})

            selected = replace(settings, model_primary=model, model_primary_effort="low", model_escalation="")
            with httpx.Client(timeout=httpx.Timeout(90, connect=10), event_hooks={"response": [capture_response]}) as http:
                client = create_model_client(selected, ledger)
                client.http.close()
                client.http = http
                started = time.monotonic()
                try:
                    result = client.generate(job_id=f"{run_id}_{prefix}", model=model, effort="low",
                                             system=SYSTEM_PROMPT, user=user, schema=RESEARCH_SCHEMA,
                                             schema_name="finn_research", max_output_tokens=max_output)
                except (BudgetExceeded, ModelUnavailable) as exc:
                    record = {"case_id": case["case_id"], "model": model, "status": "blocked",
                              "error": str(exc), "elapsed_s": round(time.monotonic() - started, 3)}
                    results.append(record)
                    stop = True
                    (out / f"{prefix}.provider.json").write_text(json.dumps(captured, indent=2))
                    continue
            duration = round(time.monotonic() - started, 3)
            packet = {p["passage_id"]: p for ps in case["sections"].values() for p in ps}
            removed = []
            validated = {name: [claim.model_dump() for claim in validate_claims((result.data or {}).get(name, []), packet, types, name, removed)]
                         for name, types in SECTIONS.items()}
            probe_results = probes(case["case_id"], result.data or {}, validated) if result.data else {}
            record = {"case_id": case["case_id"], "kind": case["kind"], "model": model,
                      "status": result.status, "elapsed_s": duration, "usage": result.usage,
                      "automatic_probes": probe_results, "removed_claims": removed,
                      "manual_review_status": "pending", "error": result.error}
            (out / f"{prefix}.input.txt").write_text(user)
            (out / f"{prefix}.provider.json").write_text(json.dumps(captured, indent=2) + "\n")
            (out / f"{prefix}.output.json").write_text(json.dumps({"record": record, "raw_output": result.data,
                                                                   "validated_claims": validated}, indent=2) + "\n")
            results.append(record)
            (out / "results.json").write_text(json.dumps({"run_id": run_id, "prompt_version": PROMPT_VERSION,
                                                           "results": results}, indent=2) + "\n")
            print(case["case_id"], model, result.status, duration, result.usage.get("cost_usd_list_price"),
                  "probes", sum(probe_results.values()), "/", len(probe_results), flush=True)
    estimate = ledger.query_one("SELECT COALESCE(SUM(COALESCE(actual_usd,reserved_usd)),0) AS n FROM model_calls WHERE job_id LIKE ?", (run_id + "%",))["n"]
    report = {"run_id": run_id, "prompt_version": PROMPT_VERSION, "fixture_version": fixture["fixture_version"],
              "models": args.models, "effort": "low", "case_count": len(cases), "additional_usage_estimate_usd": estimate,
              "sub_budget_cap_usd": args.max_usd, "global_api_cap_usd": settings.api_budget_usd,
              "results": results, "manual_review_status": "pending",
              "limits": ["Automatic probes are not semantic entailment checks.", "No hosted/cold-source discovery tested here.",
                         "This tests the writer; financial comparisons remain disabled."]}
    (out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Saved", out, "additional estimated usage USD", estimate, flush=True)
    return 0 if all(r["status"] == "completed" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
