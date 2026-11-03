# FINN build status

Updated 3 November 2026 (IST). **130 backend tests and both frontend builds (live + static) pass; the static snapshot demo is verified end-to-end on a mobile viewport. A free, never-sleeping phone demo and a genuinely useful keyless research path are now implemented and locally verified. Deployment, commit/push and submission remain approval gates — nothing has been committed, pushed, publicly deployed or submitted.** Earlier dated entries are historical; the latest entry supersedes their current-state claims.

## 3 November 2026 (later) — keyless source brief, free Gemini, free static phone demo (Claude Code)

Continuation per `docs/HANDOFF_CLAUDE_CODE.md` and the user's instruction to make the product free,
phone-ready, genuinely useful, and ready to submit today. **Implemented and locally verified:**

- **Keyless extractive source brief** (`backend/finn/brief.py`): for a fresh question with no model,
  FINN now returns the verbatim sentences most relevant to the question from each eligible primary
  source — labelled with document, period and speaker, cited to the exact passage — plus deterministic
  suggested follow-ups that re-run retrieval. Quotes are exact source slices (verified **33/33**
  verbatim across INFY/CERA/HDFCBANK against stored passage text); figures quoted, never computed.
  Replaces the previous raw-passage dump. Rendered in `ResearchView.tsx`. Tests: `test_brief.py`.
- **Free AI synthesis via Google Gemini free tier** (`backend/finn/llm.py` `GeminiClient`, OpenAI-compatible
  endpoint): on-demand research can route through `gemini-2.0-flash` at **zero per-token cost** behind the
  same citation/number/speaker validation; a 429/auth failure raises `ModelUnavailable` and degrades to the
  keyless brief. Config: `FINN_MODEL_PROVIDER=gemini`, `GEMINI_API_KEY`. Priced at $0. Tests: `test_gemini.py`.
  **Not verified over the network** (no free key was created; coding credentials are not borrowed).
- **Free, never-sleeping static phone demo** (`backend/finn/snapshot.py`, `finn export-static`; `VITE_STATIC=1`
  build; `api.ts` static resolver): exports the verified read models to ~2.1 MB of JSON (15 companies, 3 saved
  briefs, 51 cited evidence passages, 28 documents) that the React app serves from any free CDN with **no
  backend**. On-demand research, custom dates and threshold tuning are cleanly disabled with honest notes.
  Evidence links resolve to original source URLs (hashes preserved). Verified in the in-app browser at 375px:
  Push digest, company view (INFY quarterly 40,925 / 9,663 / 7,038), saved brief with cited claims, full
  evidence sheet (passage + proof + hash), and graceful static-mode gating all work.
- **Live free market data** (`backend/finn/sources/live_eod.py`, `/api/live-prices`, `finn live-prices`): an
  optional live end-of-day snapshot for the portfolio from Yahoo Finance's free public chart JSON (no key, no
  yfinance/pandas — direct httpx), flagged with the same deterministic anomaly rule. **Verified live over the
  network**: 15/15 NSE holdings fetched, 3 flagged for volume; rendered as a lazy-loaded "Live market snapshot"
  card in the live app (hidden in static mode). Deliberately separate from the verified replay — live rows are
  never written to the store, and the UI labels them as raw live Yahoo EOD with no filing-causation claim.
  Tests: `test_live_eod.py` (mocked transport).
- **Phone sharing**: in-app **Share** button (Web Share API / clipboard, deep-links to the current view);
  `scripts/make_qr.py` (segno) generates a QR PNG/SVG + printable share card for any URL; `docs/DEPLOY_FREE.md`
  documents the two-tier free deployment. `.env.example`, `README.md`, `render.yaml`, covering email reconciled
  to the keyless/Gemini default.

**Actually checked (this session):** `pytest -q tests` with all model keys unset → **130 passed**, one
Starlette/AnyIO deprecation warning. Live `npm run build` and `VITE_STATIC=1 npm run build` both pass.
`git diff --check` clean. Static demo click-through verified on a 375px mobile viewport. SQLite backed up via
the backup API to `data/verification/backup_2026_11_03_claudecode/`. **Not verified:** live Gemini network
call, hosted NSE access, real public deployment, inactivity behaviour, and a physical second-device test.

## 3 November 2026 — trust/workflow verification and Claude Code handoff

The user confirmed an ENAM deadline extension and requested continuation in Claude Code. Read
**[the detailed Claude Code prompt](docs/HANDOFF_CLAUDE_CODE.md)** for the complete current state,
PDF acceptance matrix, keyless architecture requirements, reliable hosting/mobile sharing plan,
remaining gates and approval boundaries. It supersedes the old GPT handoff and API-dependent
deployment instructions. The revised deadline was not supplied.

**Implemented locally:** selectable historical Review periods, company/type/attention filters,
actual routine filing records, persistent preferences/review context, discoverable genuine saved
briefs, explicit custom questions and follow-ups. Financial validation now checks metric labels,
numeric boundaries, supported column order, dates, units/basis, signs and exact metric-specific
source pages. Quarterly GET is read-only; extraction requires an explicit POST. Comparison gates
are stricter about speakers, chronology and entity/currency scope. Discovery repairs unsupported
archive attempt budgeting and rejects misleading BRSR/short annual-report candidates. Management
profiles and primary-source evidence contracts remain intact. All changes are in the working tree.

**Actually checked:** final key-disabled suite **119 passed**, one dependency deprecation warning;
official TypeScript/Vite build passed. The retained isolated local read-only restart report is
**17/17**, with no additional model calls (`data/verification/final_readiness_smoke.json`). Keyless
cold discovery from identity data only retrieved an annual report and two transcripts each for
POLYCAB and ASIANPAINT. Use the **corrected** ASIANPAINT report under
`data/verification/cold_discovery_2026_11_03_corrected/ASIANPAINT/`; the first ASIANPAINT run
falsely admitted a BRSR and is superseded. These are local source checks, not hosted or fresh
reasoning certification. The newer UI was exercised selectively; the older 21-layout pass below
does not certify every subsequent UI change.

**API access checked once:** 3 November, model listing HTTP 200; one minimal Messages request
HTTP 400 because the Anthropic credit balance is too low. The credential is recognised; expiry
was not established. No purchase, recharge or credential/billing change. Sanitised result:
`data/verification/anthropic_access_2026_11_03.json`. Ledger now **105 recorded calls / $0.7947052
estimated actual cost**, including the rejected $0 probe. Caps remain **$5 total / $0.25 per job**;
no more API spend is authorized by this handoff.

**Important remaining work:** saved generated briefs and cached metrics work without keys, but
fresh keyless research currently falls back to source passages. A useful, concise fresh keyless
research path still needs implementation and verification; do not call the entire application
API-independent yet. Container/host memory, hosted source access, public HTTPS access, persistent
restart on the host, a static backup, physical-phone testing, reviewer repo/history access and final
submission remain pending. No Docker/Podman is installed locally. The paid Render proposal and its
old prices are unapproved; update its key requirement before applying anything.

**Processes:** no listener on 8000; the isolated key-disabled UI server on 8765 (PID 42355, copied
store `/private/tmp/finn-final-ui-_htenjd7`) was stopped for handoff. Inspect listeners again before
starting. Its extra test jobs are not production saved examples.

## 31 October 2026 — M3 management profiles + M4 local polish (Codex)

**Management change:** new deterministic `finn/management.py`, `App.management_changes`,
`GET /api/companies/{symbol}/management`, and `ManagementCard` on company pages. A named
appointment must link to an eligible primary exchange filing. Name, role and effective date
are copied from its appointment clause; up to three complete profile sentences form a contiguous
quote from its Brief Profile section. Each field group has a separate page-located evidence button.
Missing or ambiguous fields yield no profile. No model, outside biography or ticker-specific rule.

- **HDFCBANK:** Sanjay D’Souza, role and 8 Apr 2025 effective date from PDF p.1; profile from p.2.
  The filing says **inclusion in senior management**, which is preserved rather than implying a new hire.
- **CERA:** Ramesh Baliga, Chief Business Officer role and 24 Feb 2025 effective date from p.1;
  education, experience and prior employers quoted from p.2.
- Both filings **predate the 17–30 Apr review window**. They are labelled “Before review window” on
  the company page and are not inserted into that window's digest. This is selected stored context,
  not a complete management history. INFY returns no profile, honestly.
- Every returned field was checked against its own stored passage; evidence versions and company
  identity matched. Fresh deterministic snapshots: `data/verification/m3_management_{HDFCBANK,CERA,INFY}.json`
  (ignored by Git, as is the source corpus).

**Classification:** board/director mentions alone no longer promote dividends and record dates.
Auditor/company-secretary-firm appointments remain routine; real leadership changes remain leading.
Fresh queue calculation: **15/15 checked, 48 leading, 27 notable, 2 EOD anomalies**. The decrease from
earlier counts reflects corrected false positives, not removed filings.

**M4:** Review/Research navigation remains available on detail pages; card headings wrap on narrow
screens; company identity copy is shorter; quarterly tables show units and all distinct source
citations. Evidence sheets trap keyboard focus, lock background scrolling, close with Escape and
restore the originating control. Threshold inputs validate 0–100 and now preserve a literal zero.
Review fingerprints include flagged EOD sessions, so a later unusual session can reopen a holding.
Completed quarterly extractions that return no verified numbers are now cached too; transient model
or budget failures remain retryable. No dark-mode expansion.

**Checks actually run:**
- Baseline: **66 passed**. Final key-disabled Python suite: **86 passed**, one dependency
  deprecation warning. Includes source binding/abstention, false-positive classification, API
  company/attachment/cutoff/window gates and a no-repeat-spend quarterly-cache regression.
- Official TypeScript + Vite **`npm run build` passed**. `git diff --check` passed.
- Real local app in the browser: **7 views × 360/390/430 CSS px = 21 layout checks**, no page
  overflow, no rendered control below 43.5 px (44 px CSS target, rounding tolerance at browser zoom),
  no page error alerts; captured browser logs were empty. Views: both management cards, INFY
  quarterly, Numbers vs Narrative, saved INFY research, Review, and Research home.
- HDFC appointment p.1 and profile p.2; CERA profile p.2 verified in evidence sheets. HDFC keyboard
  focus cycling, Escape and focus restoration exercised. Zero thresholds applied (15 flagged), then
  defaults restored; Mark reviewed / Show / Undo exercised and restored.
- INFY/HCLTECH/ULTRACEMCO/HINDUNILVR quarterly results were **served from existing caches**, with
  3/3/3/2 metrics respectively. Saved INFY research was read, not regenerated. UI checks used a
  key-disabled local server to avoid further generation. Screenshots/layout log: `docs/m3_m4_ui_check/`.

**Measured spend:** ledger moved from **103 calls / $0.7940462** to **104 calls / $0.7947052**:
**$0.000659** for one automatic quarterly attempt during the initial browser visit to the old server.
Management extraction and subsequent tests/UI verification made no model calls. These are application
ledger estimates, not a provider invoice. Caps remain **$5 total / $0.25 per job**. Defaults,
`.env.example` and the un-applied Render proposal now agree with those caps; the proposal also uses
the selected Sonnet research model, low effort, escalation off. No hosting provisioned.

The final local server was restarted with the existing normal configuration, PID **72394** on
`127.0.0.1:8000`; health returned `ok`, model configured and frontend built. The management endpoint
was rechecked on that process without a model call. Browser viewport overrides were reset.

**Remaining:** unfamiliar appointment layouts are omitted; quarterly gaps noted in the handoff remain.
Browser viewport checks are not a physical-phone test. Container build, hosted retrieval and restart
persistence have not been verified in this pass. Preserve/seed ignored `data/` when eventually shipping;
review hosting and API continuity, then obtain explicit approval for each outward step. The covering
email remains a draft and needs its stale feature descriptions reconciled before final approval.

## 31 October 2026 — M2: Numbers vs Narrative (promised vs delivered), deterministic and audited

The differentiator ENAM calls out as "the kind of thing we value most": management's own guidance
lined up against the actual outcome, every figure traceable to its exact PDF page, with a hard
comparability gate before any verdict. **Built entirely deterministically — no model call, so zero
API spend; the cumulative ledger is unchanged at $0.783512.**

**Engine (`backend/finn/compare.py`, unit-tested in `tests/test_compare.py`, 11 tests).**
- Extracts guidance and outcome statements from primary-source transcripts and results filings only,
  per sentence, restricted to verified **management speakers** (an analyst restating a number on the
  call is not treated as the company's guidance). Numbers are read verbatim; each is verified to appear
  in its cited passage; segment-mix, EPS, cash-flow and quarterly figures are rejected by governing-word,
  disqualifier and plausibility checks.
- **Comparability gate**: a verdict is shown only when metric, fiscal year, currency basis
  (constant-currency vs reported) and entity match. Otherwise the card shows the sources side by side
  with the explicit reason (not comparable / outcome pending) and **no verdict**.
- **Deterministic arithmetic** only (delta vs the guided range); no model computes or judges numbers.
- **No red/green**: a calm value track shows the guided range as a band and the delivered value as an
  ink marker — position alone conveys below/within/above.

**INFY, fully audited (served live at `/api/companies/INFY/narrative`; `data/verification/m2_narrative_INFY.json`):**
- Revenue growth, FY2024-25, constant currency: **guided 4.5–5% (Salil Parekh, Q3 call, PDF p.24) vs
  delivered 4.2% (results filing, PDF p.46) = 0.3pp below the guided range**, with the **acquisition-scope
  caveat** cited to Jayesh Sanghrajka discussing in-tech/inorganic contribution (Q3 call, PDF p.6), plus a
  cross-basis note that the 6.1% reported-INR figure is deliberately **not** compared against CC guidance.
- Operating margin, FY2024-25: guided 20–22% vs delivered 21.1% = within the guided band.
- Revenue growth and operating margin, FY2025-26: guided 0–3% and 20–22%, **outcome pending** by the
  30 Apr 2025 cutoff (the correctly-handled incomparable case).

**Generalisation, verified honestly (no ticker-specific logic):** HDFCBANK returns **0 items** (its
disclosures do not state these headline guidance metrics that way); CERA returns **1 item** — a ~20%
FY2025-26 revenue-growth aspiration, outcome pending — with its segment-mix percentages correctly
rejected. Evidence: `data/verification/m2_narrative_{HDFCBANK,CERA}.json`.

**Config hardening:** `finn/config.py` now repairs a host-only `ANTHROPIC_BASE_URL` (appends `/v1` for
the official host) so a leaked shell var cannot misroute live model calls; the full suite passes with the
var present.

**Checks actually run:** Python suite **60 passed** (49 prior + 11 compare); frontend **`npm run build`
(tsc + Vite) passed**; the view was exercised in-browser at **360px and 375px** — no horizontal overflow,
evidence sheet opens to the exact PDF page with publication proof and content hash.

## 31 October 2026 — M1 completion: full 15-holding portfolio populated from real NSE sources

All 12 remaining holdings were ingested on the networked Mac with `python -m finn ingest HCLTECH
RELIANCE ICICIBANK BHARTIARTL LT MARUTI HINDUNILVR SUNPHARMA ULTRACEMCO TITAN TRENT ASTRAL`, then
EOD was backfilled for HDFCBANK and CERA (ingested earlier without price/volume). **No model calls:
ingestion is network + disk only; the cumulative ledger is unchanged at $0.783512.**

**Coverage, recorded honestly** (replay window 17–30 Apr 2025; `data/verification/m1_coverage_v1.json`):
- EOD price/volume: **9 valid trading days for all 15** holdings. The fetcher correctly rejected two
  stale/misdated bhavcopy files and two HTTP 404 days rather than accepting wrong-date rows.
- Announcements: fetched for all 15 (filing window; INFY/HDFCBANK/CERA also carry wider discovery-window
  records). Results/press-release attachment PDFs were downloaded and parsed for 12 of the 15
  (INFY, HCLTECH, RELIANCE, ICICIBANK, BHARTIARTL, MARUTI, HINDUNILVR, SUNPHARMA, ULTRACEMCO, TRENT,
  HDFCBANK, CERA). **LT, TITAN and ASTRAL had no in-window results attachment in the picked categories —
  shown as a gap, not hidden.** TRENT's board-meeting PDF extracted only partially (image-based); its
  press release parsed cleanly.
- Fundamentals (annual report + transcripts) remain pre-ingested for INFY/HDFCBANK/CERA; the other 12
  resolve fundamentals **on demand via the ticker-independent discovery path** (`finn/discovery.py`)
  when their research view is opened. No per-company URL map.

**Checks actually run this session (networked Mac, this repo's venv, keys disabled for tests):**
- Python suite **49 passed** (`python -m pytest -q tests`).
- Frontend **`npm run build` (tsc -b + Vite) passed**, exit 0 — `dist/assets/index-*.js` 252 kB
  (78 kB gzip), CSS 9.2 kB. This is the full type-check + production bundle the earlier status still
  listed as outstanding.
- Portfolio review queue (`App.portfolio_queue`, replay) across the 15: **15 checked, 15 with events,
  2 price/volume anomalies flagged (MARUTI, TRENT)**; 55 leading + 23 notable events, routine filings
  collapsed. Categories are real (results, management_change, M&A, litigation, earnings_call, …).

**Known environment issue (fixed in tooling, pending code hardening):** this Mac's shell exports
`ANTHROPIC_BASE_URL=https://api.anthropic.com` (Claude Code's own proxy var — not in `.env`, not in
repo). FINN's config appends `/messages`, producing `…/messages` instead of `…/v1/messages`, which
fails one Anthropic test and would misroute live model calls. All tooling here runs with the var
unset; config will be hardened in M2 so FINN always targets `/v1` regardless.

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
