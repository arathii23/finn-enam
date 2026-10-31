# FINN build status — Milestone 1

Updated 30 October 2026 (IST). **The connected INFY path is verified locally on real NSE data with Claude-generated research. Overall sign-off remains partial: the intended host, physical phone and complete model evaluation have not been tested.** The full assignment and Milestone 2 are not complete.

## 31 October 2026 — v1.8 source-audit repairs and the portfolio review queue (Push)

**Source-audit repairs (all four prior findings resolved; see `data/verification/m2_refresh_audit_v1_8.md`).**
Regenerated INFY/CERA/HDFCBANK with Sonnet (low effort, escalation disabled), prompt `research-m1-v1.8`,
against the real corpus. No final answer was hand-edited; the corrected results are saved as completed
jobs so the app serves them without a new model call.
- HDFCBANK "below that 90 mark": same-speaker neighbour-context retrieval now pulls the LDR-defining
  passage; the claim reads "the LDR is expected to come into the 85 to 90 range, the pre-merger level,
  in FY '27." Confirmed by rendering transcript PDF p.11 (`HDFC_transcript_p11.png`).
- CERA turnover basis: prompt + a validation check now require the reporting boundary; every figure reads
  "On a standalone basis…". Confirmed by rendering annual PDF p.48 (`CERA_annual_p48.png`, row 13 Standalone;
  split 47/36/7/10).
- CERA target conditions: both retail-growth and market-recovery conditions and the year-end reassessment
  are retained; a fiscal-token validator false-positive that had been dropping this claim was fixed.
- Model-evaluation honesty: small-sample, source-reviewed result only; no universal-accuracy claim;
  automated financial comparisons remain disabled.

**Portfolio review queue (Push side) — new.** `GET /api/portfolio` and a mobile Review tab implement the
windowed digest: 15-company mock portfolio (`manifests/portfolio.json`), announcements classified into
leading / notable / routine tiers by a deterministic, explainable classifier (`backend/finn/prioritize.py`)
that maps NSE `desc` to the reference categories and refines generic "Updates" using the filing
subject/attachment (so a transcript or results filing is not buried). Configurable EOD anomaly flags
(price move ≥ X%, volume ≥ N× a 20-session average, current session excluded; disabled without enough
history; raw/unadjusted; no causal attribution to filings). Routine filings are collapsed; each event links
to its filing and to event-scoped research; reviewed/keep-watching is browser-local and keyed to the
company's current event set. Holdings with no ingested data are listed honestly as "not yet ingested".

**Checks actually run this session (in a Linux cloud workspace against a copy of the real corpus; model
calls hit the live Anthropic API with the user's key):**
- Python suite **49 passed** (40 prior + 3 new v1.8 repair regressions + 6 portfolio/anomaly tests).
- Real regeneration of INFY/CERA/HDFCBANK on Sonnet; 0 claims wrongly removed; source-level re-audit with
  two PDF pages rendered and visually inspected.
- Frontend built with esbuild; **30/30 queue UI checks** via Playwright at 360/390/430 px (summary,
  leading events, routine collapse, not-ingested section, thresholds, mark-reviewed, tab nav, no horizontal
  overflow, ≥44 px touch targets, no JS errors). Full `npm run build` (tsc type-check + Vite) still to be
  run on the networked Mac.

**Measured API usage this session:** 9 Sonnet calls, **$0.229528** (list-price estimate). Cumulative
application ledger now **$0.783512** of the $5 cap; $0.25/job cap unchanged. No caps raised.

**Environment note:** the earlier venv is a macOS/Codex build not runnable from this session's Linux shell,
and this session's shells cannot reach NSE or PyPI/npm. Model work ran in the cloud workspace against a copy
of `data/finn.sqlite3`; results and the updated DB were written back. Code files were edited in place on the
Mac. Fresh NSE ingestion of the other 12 holdings needs the networked Mac: `python -m finn ingest <SYMBOLS>`.

**Still open before submission:** ingest the remaining 12 holdings on the networked Mac; run `npm run build`
and a real-phone pass; deploy with persistent storage (not done — needs approval and cost review); export
the authentic AI conversation share links; finalise and send the covering email. Live (non-replay) research
and automated beat/miss comparisons remain out of scope.

---


The original synthetic-only report is preserved in `docs/M1_BUILD_STATUS_INITIAL.md`. The earlier claim that the user's Mac had no internet was not established: the restricted tool environment could not reach the network; later normal-network checks downloaded real sources successfully.

## Measured results

| Check | Observed result | Practical limit |
|---|---|---|
| Python logic/provider tests | **25 passed** | Synthetic fixtures and mocked endpoints; includes numeric, period, speaker and budget-recovery regressions. |
| TypeScript and Vite build | **Passed** | Actual dependencies installed, TypeScript compiled and production bundle built. |
| Real-data checks M1-01…M1-07 | **7 passed** | INFY identity, PDFs, filing, EOD, cutoff, source-page locations and generated research. The report is from the initial live-model run; refreshed source-level review is separate evidence. |
| FastAPI HTTP/startup/restart | **12/12 passed** | Actual HTTP server, frontend, endpoints, original PDF bytes and persisted job. This smoke run exercised the no-key partial path before key setup. |
| Real generated app request | **Completed** | Sonnet response through actual HTTP job `job_127ed45b67ed4215`; nine claims, two generated gaps and one follow-up manually inspected against supplied passages. One INFY packet only. |
| Browser | **Observed** | Real research rendered; guidance evidence sheet opened on PDF page 29; publication proof and conditions visible; closing restored citation focus. |
| Model requests | **7 recorded** | Four Haiku and three Sonnet; estimated list-price token usage **$0.0813745** at the recovery check. Not an invoice. |
| Physical phone / exact 360–430 px | **Not established** | In-app responsive observations do not replace phone testing. Exact requested CSS widths were not obtained from the browser override. |
| Hosted retrieval / Docker | **Not run** | Local preview only; no infrastructure provisioned or published. |

The original builder's 57 synthetic UI assertions were not rerun as that suite. Current real-browser observations are separate evidence.

## Real corpus

- NSE security master: **2,620 securities**; INFY resolved to legal name, ISIN and EQ series.
- **Nine valid EOD price/volume observations** and **12 announcements in 17–30 April 2025**. Additional announcement records support publication-proof searches and are not replay-window events.
- **Five genuine PDFs**, **3,490 passages**. Four eligible documents: FY24 annual report, January and April transcripts, April board/results bundle.
- FY25 annual report is deliberately retained and **excluded after the replay cutoff**. Exact dated NSE publication proof was found for the FY24 report.
- Replay label and evidence cutoff remain visible. Current downloads do not make the old documents live announcements.
- Raw files are content-addressed under `data/sources`; provenance, jobs and model ledger persist in `data/finn.sqlite3`.

## Repairs and model decision

- Fixed verification failure accounting: failed or partial checks cannot silently produce a successful overall script exit.
- Rejected EOD files whose internal trading dates differ from the requested date; restored valid rows. A missing report is not automatically labelled a holiday.
- Added PDF font support and refreshed extraction.
- Repaired standalone transcript speaker labels and management-roster filtering. Selected real passages identify Salil Parekh and Jayesh Sanghrajka; this heuristic remains untested across publishers.
- Added Anthropic Messages JSON-schema output alongside OpenAI Responses, provider-specific configuration and ignored local `.env` loading. Existing environment variables take precedence. The actual key is never included in reports.
- Enforced whole numeric tokens, exact period-label handling and source speaker attribution. A date label cannot support an unrelated financial amount. Citation/token checks still do not prove semantic entailment or financial comparability.
- Added conservative cumulative budget reservations; unknown-usage failures retain their reservation. Unknown-price models fail closed. No external browsing tools or cache creation are requested from the model.
- Changed parser-aware job identity and prompt version; stale or rejected research is interrupted and refreshed rather than presented as verified. Original draft snapshots remain in the verification folder.

Manual inspection rejected cheaper-model drafts for a borrowed qualifier, ambiguous rate language and a misleading evidence gap. **The private local configuration now selects `claude-sonnet-5-5`, low effort, with escalation disabled.** On the same final prompt and packet, the selected response preserved the acquisition exclusion and third-party-revenue assumption and omitted the ambiguous margin delta. No final answer was manually rewritten to make the demo succeed.

This is an initial model choice from one packet. The ten-packet evaluation specified in the prebuild document remains outstanding. Automated expectation/outcome judgments stay disabled.

## Inspect the working result

While the local server remains running:

**http://127.0.0.1:8000/#/c/INFY/research/job_127ed45b67ed4215**

To restart locally:

```bash
cd /Users/aadityarathi/Downloads/ENAM_Holdings
. .venv/bin/activate
cd backend
python -m finn serve
```

The user's Claude key is saved privately in the ignored root `.env`. No key needs to be pasted into chat. After the user authorised using the available credits, the local application development cap was raised to **$5 total, $0.25 per job**, with no escalation. The earlier $0.10 test cap caused the screenshot's failure because the next request's conservative reservation exceeded the remaining allowance. This was not a provider-balance error.

The screenshot's request was retried through the browser and completed in about eight seconds as `job_f086215b7e674b9f`. It retained five source-cited claims, removed one mixed-speaker claim, and displayed the relevant evidence gaps. Repeating the same request reused that completed job with no additional model call. Old partial attempts remain truthful historical records; refresh their page and use **Retry research**, or open the recovered result:

**http://127.0.0.1:8000/#/c/INFY/research/job_f086215b7e674b9f**

The user clarified that **API credits expire in two days**. This does not establish the exact expiry time, account balance or subsequent evaluation date. Saved results persist independently of another model call, but new research requires valid credentials and funded access. See `docs/NEXT_STEPS.md`; no expiry bypass, provider purchase or public deployment was performed.

For verification without model spending, environment overrides disable both keys:

```bash
OPENAI_API_KEY='' ANTHROPIC_API_KEY='' bash scripts/m1_verify.sh
```

A data-only run correctly marks generation partial and exits nonzero overall. The full script installs dependencies and downloads public sources; with a configured key it may also make runtime model requests.

## Evidence files

- `data/verification/m1_checks.json` / `.md`: initial live-model real-data checks, seven pass.
- `data/verification/startup_smoke.json`: 12 passing HTTP/startup/restart checks before key setup.
- `data/verification/m1_real_research_sonnet.json`: complete final HTTP response, including citations, usage and excluded documents.
- `data/verification/m1_generation_review.md`: every selected claim reviewed, earlier failures, model comparison and limits.
- `data/verification/m1_real_research.json`, `m1_real_research_v1_4.json`, `m1_real_research_v1_5.json`: earlier drafts, including rejected/partial output; not certified answers.
- `data/verification/m1_browser_observations.json`, `m1_real_preview.jpg`, `m1_guidance_evidence.jpg`: actual browser observations/captures.
- `data/verification/ingest_report.json`, `m1_verify.log`, `pip_freeze.txt`, `local_verification_summary.json`: source, environment and verification records.
- `data/verification/m1_budget_recovery.json`, `m1_budget_retry_research.json`, `m1_budget_recovered.jpg`: actual retry, completed response, deduplication check and browser proof after increasing the local limit.
- `frontend/package-lock.json`: installed frontend dependency lock.

`data/` is ignored by Git. Evidence files need deliberate packaging for independent review; they are not automatically included in a future repository submission.

## Remaining gates and next phase

1. Run the ten-packet source/abstention model evaluation. One accepted response is insufficient for an accuracy claim.
2. Test a real phone and retrieve sources from the intended deployment host. The hosted part of the first connected-path gate remains open.
3. Milestone 2: general document discovery and two successful cold non-demo/non-IT company paths; verified third demo company; 15-holding review queue; replay/live separation and current-source checks. HCLTECH January publication proof and POLYCAB coverage remain unresolved.
4. Verify investor task usefulness, operational budget/latency and deployment persistence before calling the prototype submission-ready.
5. Export/share authentic AI conversations and test reviewer access. `docs/BUILD_HISTORY.md` is a supporting index, not a substitute for those records.

**Next concrete task:** prove general document discovery on two unfamiliar companies before expanding the portfolio interface. Keep automated financial comparisons out until their independent evidence gates pass.
