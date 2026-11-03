# FINN — detailed Claude Code continuation prompt

Prepared 3 November 2026 (IST). This is a continuation of the existing working tree, not a new build.
The user confirmed that ENAM has granted a deadline extension; the revised due date was not supplied.
This document supersedes current-state claims in the older GPT handoff, deployment proposal and
31 October checklist. Historical records should remain intact.

## The user's instruction

Continue FINN in `/Users/aadityarathi/Downloads/ENAM_Holdings`, which you already have access to.
First make a proper plan against both assignment PDFs, then implement and verify the remaining work.
Make the product useful for investment professionals, easy to open on any phone, and ready for a
strong submission. The submitted application must work **without a Claude API key, API credits,
or any other paid model API**. Prepare reliable hosting that does not sleep after inactivity.
Provide a shareable HTTPS link and QR code; prepare a portable review backup as well.

The ambition is a standout, source-grounded product. Do not promise a score, invent bonus criteria,
or trade correctness for apparent feature breadth. Do not merely propose changes and stop: finish
the authorized local implementation, verification and submission preparation. Paid or public steps
remain approval gates after the concrete package is ready for review.

## First: inspect and preserve

1. Read both authoritative PDFs in the project root:
   - `1. ENAM_AI_Engineer_Build_Challenge_Main.pdf` (4 pages).
   - `2. ENAM_AI_Engineer_Build_Challenge_Reference.pdf` (3 pages).
2. Read this document, the latest entry in `BUILD_STATUS.md`, `docs/FINAL_POLISH_PLAN.md`,
   `docs/BUILD_HISTORY.md`, `docs/MODEL_EVALUATION.md`, and `README.md`. Use the older
   `docs/HANDOFF_GPT.md` and prebuild specification as history, not as the present task list.
3. Run `git status --short` and inspect the full diff, including untracked files. Much of M1–M4
   is uncommitted. Do not reset, clean, overwrite, or discard this work.
4. Back up the main SQLite store consistently using SQLite's backup API, and preserve
   `data/sources`, saved results, caches, ledger, verification reports and authentic AI history.
   `data/` is ignored: a repository checkout alone does not contain the current demonstrations.
5. Inspect listeners before starting a server. At handoff, no server is listening on 8000;
   the isolated test server on 8765 was stopped. Old documents naming a running server/PID are stale.

No `AGENTS.md` was found in the workspace or its ancestor directories during this pass. Respect any
applicable instructions you find subsequently and the user's existing authorization boundaries.

## Confirmed API situation — do not repeat the probe

On 3 November, a single minimal generation test was made with the existing local Anthropic key:

- Listing models succeeded, HTTP 200: the credential is recognised.
- A single Messages request was rejected, HTTP 400, `invalid_request_error`: the account's
  **credit balance is too low to access the API**. This establishes a funding problem, not key expiry.
- No credit purchase, recharge, credential change or billing change was made.
- Sanitised report: `data/verification/anthropic_access_2026_11_03.json` (ignored).
- Probe ledger entry: `call_9e2e6bd3e1d24212`, status `access_probe_http_400`, actual estimate $0.
- Current main ledger: **105 recorded calls, $0.7947052 total estimated actual cost**. The count
  includes the rejected probe. These are application estimates, not a provider invoice.

The user's decision is to remove application runtime dependence on that account. Do not spend more
credits, test another paid provider, raise limits, or ask the evaluator for a key. Preserve the old
adapters and genuine saved outputs where useful, but make the keyless path the shipped default.
Existing caps remain **$5 total / $0.25 per job**; they are ceilings, not permission for further spend.

Claude Code's own login is separate from the deployed application. Check `/status` in Claude Code.
A valid Claude subscription can support coding even when Console API credits are exhausted, subject
to that plan's limits. An approved environment API key can take precedence over subscription login;
inspect the active method without printing credentials or changing login automatically.
See [official authentication guidance](https://code.claude.com/docs/en/authentication).

For this substantial continuation, use `/model best` with `/effort high` if available within your
account's allowance; the current `best` alias selects Fable where available and otherwise Opus.
`/model opus` is a strong practical choice for planning and trust review. `/model opusplan` uses
Opus for Plan Mode and Sonnet for execution when conserving usage. Confirm the actual selection in
`/status`; do not copy old model version names blindly. This is a recommendation, not a benchmark
or a guarantee of access. [Official model configuration](https://code.claude.com/docs/en/model-config).

## What the assignment actually evaluates

There is **no numerical rubric or weighted scorecard** in the PDFs. The stated evaluation is
building ability, creativity, product sense, judgment and architecture. Useful density, concise
presentation, interaction, primary evidence and efficiency support those goals. Efficiency explicitly
earns bonus points; other additions below are product choices, not claimed official bonus awards.

| Requirement or example | Current position | Required finish / honest boundary |
|---|---|---|
| Mobile-first usable prototype | Responsive React/FastAPI app exists | Public phone URL, final real-device verification, complete useful journeys |
| 15–20 mixed portfolio companies | 15 genuine NSE holdings populated | Preserve identity/coverage; do not call missing data an all-clear |
| Three source types | EOD, exchange filings, annual reports/transcripts work locally | Preserve source dates; test hosted source access and cached fallback |
| Push digest, default 24h, chosen period | 24h/7d/all/custom historical replay and filters implemented | Clear cutoff everywhere; applied dates/counts must agree |
| Configurable triggers | In-app historical EOD threshold flags work | Disclose session/baseline; do not claim delivered or real-time alerts |
| Management background example | HDFCBANK and CERA primary filing profiles work | Keep exact source/date/context; unsupported layouts abstain |
| Quarterly example | Verified cached Revenue/PBT/PAT for three companies; PBT/PAT for one | Address Revenue, EBITDA, PBT, PAT individually; show justified omissions, comparable prior values, QoQ/YoY only when supported |
| Pull, roughly 3–5 demonstrations | Three genuine generated saved briefs: INFY, CERA, HDFCBANK | Keep discoverable, clearly saved and fully cited; add no canned outputs disguised as fresh research |
| Any NSE ticker where data exists | Generic discovery/retrieval; two keyless cold source checks passed locally | Fresh keyless research must be useful beyond the saved demo set; prove it from an empty store |
| Primary sources only for Pull | Identity, publication and citation gates exist | No news, broker notes, secondary financial tables or model memory |
| Numbers vs narrative example | Annual guidance/outcome comparison, available two-call history | Label actual scope; a full last-four-quarter tracker is not implemented |
| Repository, build history, covering email | Working tree and local drafts exist | Approved publication, authentic accessible history and final links still pending |

The reference has 17 announcement categories; it explicitly allows adaptation. Preserve sensible
classification and access to every stored filing rather than implementing one elaborate card per
category. The eight Pull outputs are a **menu**, not eight mandatory polished features:

- Business snapshot: saved cited research plus a useful keyless extractive view.
- Financial snapshot: verified quarterly tables; expand only where units/periods/basis are proven.
- Trajectory, balance sheet and cash quality: only build supported comparisons or literal source
  sections if they materially improve the chosen journey; otherwise record these omissions.
- Narrative vs numbers and guidance: existing deterministic comparisons and exact management quotes.
- Bull vs bear: any eventual interpretation must link to evidence and distinguish inference from fact;
  a fabricated two-sided template is worse than omitting this optional output.

The main PDF's email destination is `assessment@enam.com`; required subject is
`ENAM - IIT screening - 2027`. Prepare the covering note; do not send it without explicit approval.

## Current architecture and working features

Backend: Python 3.12, FastAPI, SQLite/FTS, content-addressed source PDFs and bounded research jobs.
Frontend: React 19, TypeScript and Vite, currently served by FastAPI on one origin. Retain this stack
unless a narrowly justified change is necessary. No framework rewrite for appearance alone.

Important backend modules: `backend/finn/{api,service,config,db,replay,discovery,research,llm,
prioritize,compare,quarterly,management}.py` and `backend/finn/sources/{documents,fetch,nse}.py`.
Important UI: `frontend/src/{App,QueueView,CompanyView,ResearchView,NarrativeView,ManagementCard,
ResearchComposer,SavedResearch,EvidenceSheet}.tsx`, `api.ts`, `styles.css`, `research.css`.

Portfolio: INFY, HCLTECH, RELIANCE, HDFCBANK, ICICIBANK, BHARTIARTL, LT, MARUTI, HINDUNILVR,
SUNPHARMA, ULTRACEMCO, TITAN, TRENT, ASTRAL, CERA. Stored replay is April 2025, ending
30 April 2025; it is **not a live November 2026 feed**. All 15 have stored announcements and
nine EOD sessions. Results attachments exist for 12/15; LT/TITAN/ASTRAL have in-window gaps.

Implemented during the latest trust/usability pass:

- Review period selection, company/type/attention/EOD filters, progressive disclosure, actual routine
  filings and attachment links, persistent preferences and review state, undo and restored context.
- Shorter source-derived subjects with original descriptions available; no invented event summaries.
- Research composer (300-character bound), suggested questions, explicit follow-up submission,
  question/context preservation and real saved-result discovery through `/api/research/saved`.
- Quarterly GET is read-only; model extraction is a separate explicit POST. Revalidated cached
  metrics bind to their own cited page. Exact tokens, metric labels, dates, units, basis, signs and
  supported table column order are checked. EBITDA requires an explicit label; no guessed proxy.
- Comparison gates reject unsupported speaker attribution, chronology, metric/entity/currency
  mismatch and preserve limitations. Unknown entity scope is conspicuous. No ticker-specific rules.
- Management cards use genuine linked appointment filings: HDFCBANK Sanjay D'Souza, inclusion in
  senior management, effective 8 April 2025; CERA Ramesh Baliga, effective 24 February 2025.
  Role/date evidence is on PDF p.1; profile on p.2. Both predate the digest window and say so.
- Dividend/record-date, auditor-firm, newspaper/compliance and personal shareholding classification
  false positives repaired. Priority reasons still need source-grounded judgment.
- Discovery skips known unsupported archives without wasting its finite PDF budget, prioritises
  dated candidates, and body-checks ambiguous annual-report candidates. A BRSR referencing an annual
  report must not become a full annual report. Preserve the regression for this actual failure.
- Evidence sheets have source locators, publication proof, original/cached PDF actions and hashes,
  plus focus trapping, Escape, focus restoration and background scroll locking.

Genuine completed saved research in the main DB:

| Company | Job ID |
|---|---|
| INFY | `job_ef82f56b1af94761` |
| CERA | `job_0a5a2ecb657844ab` |
| HDFCBANK | `job_f471c0c3739c4e75` |

These IDs are audit pointers, not values to hard-code in UI or query-specific business logic.
Cached quarterly metric counts are INFY/HCLTECH/ULTRACEMCO/HINDUNILVR = **3/3/3/2**. Current actual
evidence pages are **378/2/2/6** respectively. INFY's unsupported QoQ was removed; YoY remains.
Some source pages do not identify currency or consolidation basis clearly: disclose/omit, don't infer.
The INFY comparison has four cards, including pending future outcomes; do not advertise four complete
quarters of tested promises. Historical showcase numbers in older notes must be rechecked against
current validated output rather than copied into marketing.

## What is verified, and what is not

Latest local checks on 3 November:

- **119 backend tests passed**, one Starlette/AnyIO dependency deprecation warning.
- Official frontend TypeScript + Vite production build passed (41 modules).
- `git diff --check` passed before this documentation update; repeat before finishing.
- A retained local GET-only restart report passed **17/17** checks with model calls disabled:
  `data/verification/final_readiness_smoke.json`. It verifies saved jobs, individual quarterly
  evidence and source hash persistence on an isolated local copy; its old temporary directory is gone.
- Keyless cold discovery started from security-master data only, no seeded document URLs or passages:
  POLYCAB retrieved a 262-page annual report and two transcripts; corrected ASIANPAINT retrieved a
  272-page full annual report and two transcripts, excluding a misleading BRSR. Zero model calls.
  Reports/source snapshots are under:
  - `data/verification/cold_discovery_2026_11_03/POLYCAB/`
  - `data/verification/cold_discovery_2026_11_03_corrected/ASIANPAINT/`
  **Do not cite the first ASIANPAINT report in the uncorrected directory as success**: it admitted
  the 51-page BRSR and is superseded. These checks prove local discovery, not fresh model reasoning.
- The earlier 31 October UI pass covered 21 layouts (seven views × 360/390/430 CSS px), documented
  in `docs/m3_m4_ui_check/`. The newer workflow was exercised selectively, including filters,
  routine links, review/undo, saved research, quarterly evidence, follow-up and composer submission.
  **The full three-width sweep was not repeated after the latest changes.**

Still unverified or unfinished:

- A polished fresh keyless research workflow: current model-unavailable requests show retrieved
  passages rather than a newly generated synthesis. Do not call that finished merely because it fails gracefully.
- API-independent extraction of new quarterly layouts; existing caches were originally generated
  with a model and are now validated/read without one. Separate cache reuse from fresh extraction.
- Container build/run (Docker and Podman are not installed here), host memory and hosted NSE access.
- Public hosting, restart persistence on that host, browser URL/QR sharing and real-phone testing.
- Final updated UI/accessibility sweep, reviewer access to repo/history, deployment and submission.
- No commit, push, paid resource, public deployment or email submission has been made by this pass.

## Priority 1 — make keyless use a complete product path

Plan the smallest credible implementation, then build it. Reuse the existing generic discovery,
source identity/publication checks, FTS retrieval, deterministic comparison and evidence contracts.

1. Introduce a clear application mode/capability contract that guarantees no model calls in the
   default submission configuration, even if a developer happens to have API keys in their shell.
   Do not rely solely on `model_configured` or the presence/absence of a secret. Keep optional model
   support isolated for a future explicitly enabled configuration; never borrow Claude Code credentials.
2. Keep saved, historically generated briefs readable with generation date, source cutoff, citations
   and truthful provenance. Reading them, navigating and loading a company must make zero model calls.
3. For a fresh ticker/question, discover primary sources and return a useful **source brief**:
   resolve identity, rank relevant sections, select concise verbatim sentences/management quotations
   with enough surrounding qualifications, identify periods, show supported deterministic facts,
   and expose gaps and exact evidence. Label it as extracts/computed facts; don't pretend an LLM
   wrote a new analytical conclusion. Use a generic query-aware ranking/selection pipeline rather
   than hard-coded answers, company templates, or dumping dozens of raw passages onto the phone.
4. Keep custom questions and follow-ups meaningful in keyless mode. They should change retrieval
   and expose the most relevant available evidence, retain context, and support a clear next action.
   Unsupported questions should explain the specific missing source/period/metric, preserving useful
   evidence, rather than displaying a permanent API error or spinning indefinitely.
5. Add conservative deterministic financial extraction for clearly supported tables if needed to
   make fresh results useful. Keep the existing validator as a floor: same metric, period, units,
   reporting basis and entity scope; signed numeric values; zero/negative comparison handling.
   Never infer EBITDA from PBT/PAT or silently compare a year with a quarter.
6. Use bounded source retrieval, caching and deduplication; prevent repeated refreshes from downloading
   or parsing indefinitely. Expensive actions stay explicit, with visible progress and cancellation
   or bounded termination. A blocked exchange must leave the existing demo usable.
7. Do not add local model inference by default: a free model still needs CPU/RAM and deployment work.
   If extractive research cannot satisfy a material chosen workflow, document that limitation and
   present a concrete local/self-hosted alternative with resource measurements before any paid step.

The honest trade-off is deliberate: source-grounded extracts and computations can work without
model credits; arbitrary open-ended synthesized reasoning is not automatically equivalent to Claude.
The brief allows any model/tool choice. Demonstrate engineering and product judgment, not fake AI.

## Priority 2 — professional mobile workflow

Optimize for an analyst or portfolio manager checking a filing between meetings:

- Lead with what changed, when, why it earned attention, and the one useful action. Keep supporting
  detail expandable. Preserve a calm, dense design and the existing Review/Research navigation.
- Every date must mean one thing: chosen review period, trading session, reporting period, filing
  publication time, or saved result generation. Keep historical replay unmistakable, using IST where
  appropriate. Relative “24h” labels are anchored to replay cutoff, not today's date.
- Let users scan material items, filter by company/category, reveal routine filings, mark reviewed,
  undo, open a company, inspect exact evidence and return without losing filters or scroll position.
- Tables must stay readable on 360/390/430 px screens: explicit units/basis, current and prior
  values, QoQ/YoY labels, and a reason for every omitted metric. Use local horizontal scrolling only
  where helpful; no page-wide overflow or tiny tap controls.
- Show coverage and partial states plainly. A source retrieval gap is not “nothing happened.”
  Avoid unexplained extraction/API/debug language in the professional's main flow.
- Keyboard and touch accessibility: labelled controls, visible focus, sensible contrast, modal
  focus/close/return, adequate targets, loading/empty/error states and preserved questions.
- Share links should open the intended company/brief on a new phone without login, the user's
  laptop, a local server, or a browser state dependency. No account requirement for assessment browsing.

## Priority 3 — hosting, phone sharing and a durable fallback

Prepare a concrete hosting proposal and working local packaging first. Do not provision it yet.

Recommended main deployment: **one paid Render web service with a persistent disk**, serving the
existing API and React app on HTTPS. Paid compute does not spin down on inactivity; SQLite and
source PDFs must both live under the persistent mount. Maintain one instance/worker for the current
SQLite/job design. Official references: [Render FAQ](https://render.com/docs/faq),
[persistent disks](https://render.com/docs/disks).

- Existing `Dockerfile` and `render.yaml` are proposals only. The blueprint currently asks for an
  Anthropic key: update it for the new keyless default before deployment. Do not blindly apply it.
- Confirm current provider prices, disk/corpus size, bandwidth terms and memory measurements.
  The old document's approximate $7.50/month is historical, not a verified quote. The prebuild's
  $15 first-month ceiling is a proposal, not authorization to buy. Quote costs before approval.
- Parsing the largest reports may exceed a 512 MB instance. Test the actual largest selected input
  under realistic concurrency; pre-seed audited sources and bound fresh parsing. If a larger plan
  is necessary, report it and obtain approval rather than quietly provisioning or losing generic use.
- Prepare safe, versioned data transfer: a consistent SQLite backup, required content-addressed
  PDFs, integrity manifest and saved-output provenance. Never upload `.env`, credentials or an
  indiscriminate copy of private development/conversation files. Prove the seed restores cleanly.
- Configure bounded jobs, health/readiness checks, graceful shutdown and persistence. Test both
  saved research and exact evidence after service restart. A process-health response alone is insufficient.
- Test the hosted exchange path: local success does not establish that NSE accepts a datacenter IP.
  Preserve explicit cached/replay access and source-failure states if new retrieval is blocked.
- Do not promise 100% uptime: disk-backed services can have brief maintenance downtime.
  [Render maintenance documentation](https://render.com/docs/platform-maintenance).

Prepare a **static read-only submission snapshot** for resilient evaluation, ideally on a CDN such
as Cloudflare Pages, as a second link or a clearly labelled fallback. It must include exported,
validated read models for Review, company details, saved research, comparisons, coverage and their
necessary evidence. A Vite bundle alone still calls FastAPI and is not a functioning static demo.
No fabricated requests or silently substituted answers. Show snapshot date and read-only scope.
Inventory PDF sizes: Pages has a 25 MiB per-asset limit; evaluate object storage or a different
permitted delivery method for larger sources without breaking evidence links or buying it silently.
[Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/).

Deliver phone sharing as:

1. A stable public HTTPS URL with a mobile landing state and direct brief/company links.
2. A downloadable QR image for that URL and a simple “Share”/copy-link action.
3. Optional installable PWA behavior, if it adds value: manifest/icons, standalone layout, safe
   versioned caching and an explicit offline/snapshot state. Installation must not be required.
4. A portable backup: concise PDF demo guide with clickable sources/QR and/or packaged static
   snapshot with honest opening instructions. Sending SQLite, a source ZIP or raw `index.html`
   does not make the current full application usable on an ordinary phone.

Don't use a sleeping free backend or keep-alive pings as the reliability strategy. If paid hosting
is declined, prepare a CDN-hosted keyless snapshot and clearly disclose which interactive research
features require a live backend. Zero LLM charges and zero hosting charges are separate choices.

## Priority 4 — useful extras after core gates pass

Favor a small number of demonstrable additions: source hash/provenance verification, saved and
shareable briefs, source freshness/coverage, a readable offline snapshot, a reproducible evaluation
report and measured zero-model-call operation. Avoid voice, decorative charts, arbitrary confidence
scores, invented investment ratings, or more research sections just to appear complete.

If adding a four-quarter promises tracker, first retrieve four properly dated transcripts/results
and prove entity/metric/year/currency comparability. Otherwise retain the existing bounded annual
comparison and explain that choice. Do not relabel two calls as four quarters.

## Execution plan and acceptance gates

Before editing, produce a short prioritized plan and a PDF-to-feature matrix recording implemented,
partial, omitted and unverified items. Choose the minimum architecture for a first-class keyless
workflow and state the trade-off. Then proceed with reversible local work without asking the user
to reconfirm every implementation detail. Update the plan as evidence changes.

1. **Baseline and preservation:** inspect diff, backup ignored data, run current checks, identify
   source trust contracts and every model invocation path.
2. **Keyless runtime:** implement explicit mode, useful fresh source research, cache/provenance and
   deterministic supported extraction. Add meaningful regressions for real failure cases.
3. **Professional UX:** finish the short connected journey and final mobile/accessibility sweep.
4. **Deployment and fallback package:** test build/restore locally, prepare prices/configuration,
   publishable data manifest, public URL plan, static fallback, QR generation and phone checklist.
5. **Submission package:** reconcile all current docs, final readiness matrix, covering email draft,
   reviewer guide, repository preparation and authentic build-history links. No fake screenshots,
   measurements, share links or claims of a user study.
6. **Approval and hosted validation:** once the concrete package is reviewable, request approval for
   the specific paid/public steps with costs and scope. On approval, deploy and complete the actual
   host/mobile gates; do not stop at handing over deployment instructions when deployment is authorized.

Required evidence before calling the submission ready:

- Boot with **both provider keys unset** and the shipped keyless mode enabled. Instrument/block
  model-provider requests and assert zero model calls/ledger delta across the core journeys.
  A zero-cost rejected call is still an unwanted model dependency.
- Existing saved briefs, Review filters, management cards, available quarterly tables, comparisons,
  evidence passages and cached PDFs work without any model key.
- A new question changes relevant retrieval and produces a useful cited keyless source brief.
- At least two unfamiliar tickers tested from empty stores containing identity data only: no demo
  document URLs/caches. Report source discovery, extraction and research results separately; failures
  need precise gaps and must not be counted as successes. Preserve local-vs-host distinctions.
- Verify representative displayed numbers and quotations manually against their own PDF pages,
  including signs, periods, units, consolidation/currency basis and qualifications. Test actual
  rejection of misleading BRSR, unsupported EBITDA and annual/quarter or speaker mismatches.
- Full appropriate backend suite, official frontend build, `git diff --check`, final 360/390/430 px
  journeys, accessible evidence sheets, deep links and no page overflow. Do not invent pass counts.
- Container or actual deployment build/run, bounded memory and source downloads, clean seed restore,
  restart preserving job/source hashes, inactivity check after more than 15 minutes, and clear
  fallback behavior when backend/source access is deliberately unavailable.
- HTTPS link works on a physical phone over mobile data, separate from the development laptop.
  If no physical device is available, leave that gate unverified and give the user a concise checklist.
- Repository and authentic conversation links open with evaluator permissions. No credentials in
  commits, exported public data, frontend bundle, logs, screenshots or build-history attachment.

Useful baseline commands (from the existing project, not a new environment):

```bash
# Repo root
git status --short
git diff --stat
lsof -nP -iTCP:8000 -sTCP:LISTEN

# Backend: explicit empty keys override dotenv loading
cd /Users/aadityarathi/Downloads/ENAM_Holdings/backend
env -u ANTHROPIC_BASE_URL OPENAI_API_KEY='' ANTHROPIC_API_KEY='' \
  ../.venv/bin/python -m pytest -q tests

# Frontend
cd /Users/aadityarathi/Downloads/ENAM_Holdings/frontend
npm run build
```

For an isolated UI run, use a SQLite backup under a fresh audit directory and set `FINN_DATA_DIR`
to that copy; preserve main-store hashes/ledger. Run from `backend/`:

```bash
env -u ANTHROPIC_BASE_URL OPENAI_API_KEY='' ANTHROPIC_API_KEY='' \
  FINN_DATA_DIR=/absolute/path/to/audit-copy \
  ../.venv/bin/python -m finn serve --host 127.0.0.1 --port 8765
```

Inspect `scripts/smoke.py` before using it: the existing version submits research, so it is not a
read-only smoke. Backend changes require restarting the process. Never print or shell-source `.env`.

## Non-negotiable working boundaries

- No commit, push, public deployment, paid resource, credit purchase/recharge or submission email
  without the user's explicit approval for that outward action. Preparing/building/testing locally
  is already authorized; finish it before requesting shipping approval.
- Preserve original working-tree changes, ignored real data and genuine Claude/Codex conversations.
  A build-history summary is supplementary, not a replacement for the authentic conversations.
- Keep Pull primary-source-only and source identity/publication/cutoff validation fail-closed.
  No fabricated metric, missing-section filler, ticker-specific exception or silent basis substitution.
- No application API-key dependency, alternate paid-provider dependency, evaluator key prompt or
  dependency on the user's running laptop. Coding-tool access is a separate development concern.
- Do not claim “ready” until the applicable gates have actual evidence. At the end, report what
  changed, tests and measured costs, the actual URLs/artifacts, honest omissions and any remaining
  approval-dependent action. State explicitly whether the submission has been sent.
