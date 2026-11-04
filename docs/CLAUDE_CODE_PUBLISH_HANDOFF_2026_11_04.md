# FINN — Claude Code publishing and completion handoff

Prepared 4 November 2026 (IST). This is an execution prompt for Claude Code in the existing local
repository. Continue the current working tree; do not start a new app or reconstruct the work.

## User request and authorization

FINN has already been submitted to ENAM. After submission, the user asked to make the existing
product substantially more practical and useful for its target investors, make as many claims in
the submitted email real as possible, improve usability, and use free resources including model
providers beyond Gemini. Codex implemented and checked the changes locally.

The user explicitly answered **yes** to publishing this update to the existing GitHub Pages and
Render links, then asked to have **Claude Code perform the publishing and remaining work instead**.
You are authorized to commit and publish this update to those existing destinations and perform
the necessary bounded checks. Do not ask again merely because the app has already been submitted.
The change of executor did not authorize a new submission email, new hosting account, paid tier,
purchase, recharge, new recurring charge, or disclosure of credentials/private build conversations.

Finish the authorized work; do not stop at a plan or a suggested command list. If a specific action
truly needs the user's login, physical device or key, finish the independent work first and identify
that precise action. Do not treat an unavailable optional model key as blocking keyless publication.

## Workspace and existing public destinations

- Repository: `/Users/aadityarathi/Downloads/ENAM_Holdings`
- Existing source repo: `https://github.com/arathii23/finn-enam`
- Existing static demo: `https://arathii23.github.io/finn-enam/`
- Existing live app/backend: `https://finn-mow9.onrender.com`
- Existing scheduled price feed:
  `https://raw.githubusercontent.com/arathii23/finn-enam/live-data/live_prices.json`
- Local branch at handoff: `main`; last commit: `472813c`.
- GitHub CLI access was checked successfully using the normal network on 4 November; the existing
  repository reported `ADMIN` permission and default branch `main`. Recheck current access/state.

The upgrade is **uncommitted and unpublished**. Codex's publishing turn was interrupted before any
commit, push or deployment; only local/read-only inspection occurred. Do not assume a deploy was
started. At the end of local QA the owned servers on 8765/8876 were stopped and temporary tabs closed.
Check listeners before starting anything; do not reuse old PIDs.

## Read first, in this order

1. This handoff and the user's latest instructions.
2. `docs/POST_SUBMISSION_IMPROVEMENTS.md` — current implementation, exact verification scope,
   submitted-email claim matrix, and practical limits.
3. The **4 November** entry of `BUILD_STATUS.md`, `README.md`, `docs/FREE_RESOURCES.md`,
   `docs/DEPLOY_FREE.md`, `Dockerfile`, `render.yaml`, and `.github/workflows/live-prices.yml`.
4. Both assignment PDFs in the repository root, if you need to reassess remaining assignment scope:
   `1. ENAM_AI_Engineer_Build_Challenge_Main.pdf` and
   `2. ENAM_AI_Engineer_Build_Challenge_Reference.pdf`.
5. `docs/BUILD_HISTORY.md` and relevant source/test files.

Older `docs/HANDOFF_CLAUDE_CODE.md`, `docs/HANDOFF_GPT.md`, `docs/NEXT_STEPS.md`,
`docs/DEPLOY_BACKEND_FREE.md` and old submission checklists contain historical instructions. Some
still say the app is unsubmitted, requires an API key, lacks useful keyless answers or needs first
hosting. Those statements do **not** describe the current task. Preserve dated history, but reconcile
current deployment/setup instructions that could mislead someone. Do not blindly execute old paid
deployment proposals or revive the old expiring-credit plan. No score or expanded official rubric
should be invented from these notes.

## Preserve the work and evidence

Inspect `git status --short`, tracked diffs and each relevant untracked source file. The work covers
backend/current research, provider adapters, frontend flows and documentation, with new files not yet
tracked. Do not reset, clean, overwrite or discard the current tree, main corpus or authentic history.
Fetch and compare remote state before publishing; integrate concurrent changes carefully, without a
force push to main or the Pages publication branch. Use a `codex/` prefix if you create a work branch.

Back up the main SQLite store using SQLite's backup API and preserve `data/sources`, saved jobs,
ledger and caches. Use an isolated copy for new QA jobs and source discovery. The recent current
filings and extra research jobs under `tmp/practical_review/app_data/` are QA data, not production
showcase material. Do not replace the main database or release seed with that QA store.

Stage only reviewed application/test/documentation files. In particular:

- Never publish `.env`, keys, credentials, local database copies, private logs or notebook exports.
- `output/` was already untracked before this improvement pass; do not add it with `git add .`.
- `tmp/`, `data/`, static snapshots and built distributions are ignored for good reasons. Publish a
  deliberately prepared static build using the existing Pages mechanism, not by blanket force-add.
- Review the Docker build context and exclusions; avoid including local secrets, output PDFs or
  large temporary QA copies if testing a local Docker build.
- Preserve genuine saved briefs and publication proof. Do not globally bump the parser/prompt
  version merely to make deployment look fresh; that can invalidate original evidence and results.

## What is implemented — finish and verify, rather than rebuilding

The intended user is a self-directed Indian equity investor or research associate covering a small
watchlist. The central journey is: check portfolio notices, read a filing, ask a focused question,
inspect the exact evidence, save a cited point and follow up later. No user interviews have yet
established product-market fit; do not claim they have.

1. **Current portfolio filings:** explicit `POST /api/portfolio/refresh?days=7`, for up to 15 known
   holdings and seven IST calendar dates by default. A 45-second bounded check validates primary NSE
   metadata, has short timeouts/no retries/response caps, retains old valid data on failure, and
   reports partial states. A 15-minute cache retains original check timestamps. No PDFs/models in
   the metadata check; GET/navigation is read-only.
2. **Current-source research:** replay/current modes; bounded rechecks for annual reports and call
   transcripts; on-demand reading of the selected company-bound filing. Proven publication dates,
   identity checks and reference cutoffs gate retrieval. Fresh questions do not turn old documents
   into current evidence. Source-check times, publication dates and market-session dates are distinct.
3. **Useful keyless answers:** query-aware whole-word/topic matching, actor-specific rejection of
   irrelevant resignation evidence, exact extracts and named gaps. Quotes preserve adjacent
   conditions and page-break context. Briefs prioritize management answers for guidance questions,
   avoid repeated guidance in media/analyst bundles, and show each quote's publication date.
4. **Real transcript repair:** standalone speaker labels are recognized by both extraction and
   discovery; explicit titled call sections later in bundled PDFs can identify the reporting period.
   A cover, roster or AGM-only transcript is not an earnings call. Previously rejected bytes can be
   rechecked without globally invalidating valid saved evidence.
5. **Practical UI:** company name/symbol search, current/historical controls, draft questions,
   meaningful saved keyless briefs, touch controls, explicit evidence and static-to-live links that
   preserve symbol/question/event/mode and do not auto-submit.
6. **Notebook:** cited points, quotes, follow-ups and personal notes stay in the browser. Search,
   done/open status and Markdown export retain provenance. Saving a context-linked quote saves
   the entire cited group, including both sides of a page-break condition. It does not sync between
   the static and live origins; notes are not sent to models.
7. **Market reliability:** actual trading dates, stale/failure states, safe missing-array parsing,
   and correct previous-session handling. Unknown fields stay unknown. Replay prices are not shown
   as current alerts. Postal-ballot results do not become financial-results alerts.
8. **Free provider options:** explicit keyless default in code, Docker and blueprint; Gemini remains
   optional. Groq and free-only OpenRouter adapters use the existing evidence-validation/fallback
   path. No automatic paid fallback or borrowing of coding credentials. Read `FREE_RESOURCES.md`.

Important additions include `backend/finn/current.py`, practical research/retrieval tests,
`test_current.py`, `test_free_providers.py`, `CompanySearch.tsx`, `Notebook.tsx`,
`ResearchModePicker.tsx` and `links.ts`. Inspect the complete diff for the rest.

## What was actually checked locally

- **210 backend tests passed**, one existing Starlette/AnyIO deprecation warning.
- Live TypeScript/Vite build and static Pages-base production build passed.
- Fifteen baseline layout checks: five views at 360/390/430 CSS pixels. Six further checks covered
  the final context-linked brief and full notebook. Actual viewport widths, page overflow and visible
  action sizes were checked; these are browser checks, not a physical-phone certification.
- Real NSE portfolio check: 49 valid recent announcements, 14/15 company responses fully validated.
  SUNPHARMA retained eight valid records but an additional record failed validation, so its check
  remained partial. These are observations from 4 November, not expected constants for future runs.
- Real current Infosys research discovered FY2025-26 AR and Q1/Q2 FY2026-27 call transcripts.
  Latest cited transcript was exchange-published on 28 October 2026. Five displayed highlights were
  exact substrings of their own passages; guidance assumptions crossing PDF pp.29–30 stayed together.
- Evidence sheet for a saved Infosys result showed the AR at PDF p.337, proof and hash; closing it
  restored focus. Notebook notes, completed state and grouped citations survived UI save/reload;
  the downloaded Markdown retained both source pages, publication date, URLs, hashes and the note.
- Static site loaded under `/finn-enam/`; name search and a question containing `&` reached the
  receiving local live app intact, without starting research automatically.
- Model keys were disabled and no new model API calls, account, key or charge were made.

Evidence is under ignored `tmp/practical_review/`, especially `verification_summary.json`,
`mobile_checks.json`, `final_mobile_checks.json`, `final_source_quote_audit.json`,
`FINN_Notebook_QA.md`, `FINN_Current_Review.png` and `app_data/current_refresh.json`.
These audits are evidence of the stated checks, not permission to publish all underlying files.

Still unverified: the updated hosted deployment, Render-side source access/resource limits,
container build/run, real-key Groq/OpenRouter availability and source-level output quality, and a
physical second-device test. Neither Docker nor Podman was installed locally at the last check.
Do not install a large toolchain merely to tick a box if the existing hosted build supplies the
relevant evidence. A successful build is not a successful hosted retrieval test.

## Execute in this order

### 1. Confirm local readiness and the deployment mechanism

Inspect the current diff, preserve unrelated files, back up data and check the actual remote refs,
Pages configuration, existing Render service, its source branch and auto-deploy behavior. Only the
price-refresh workflow was found under `.github/workflows/`; do not invent a Pages deployment
workflow/branch or assume the Render dashboard is authenticated.

Re-run the appropriate local checks in your environment before publishing. The existing backend
command from the repository root is:

```bash
env FINN_MODEL_PROVIDER=keyless OPENAI_API_KEY='' ANTHROPIC_API_KEY='' \
  GEMINI_API_KEY='' GOOGLE_API_KEY='' GROQ_API_KEY='' OPENROUTER_API_KEY='' \
  PYTHONPATH=backend .venv/bin/pytest -q backend/tests
```

Run `npm run build` inside `frontend` for the live bundle, and `git diff --check`. Re-run targeted
checks after any repairs and update the recorded result rather than preserving 210 as a target.
Do not re-run paid API probes or read credentials into logs. Prepare a rollback reference to the
previous deployed source/static revision before replacing either public version.

### 2. Publish the existing Render backend first

Commit the reviewed source changes and push through the existing repo/service deployment path.
Keep the existing Render free service, URL, one worker and source corpus. Do not create a second
service, buy persistence, migrate hosts or change billing. The Docker build downloads the existing
seed release at:

`https://github.com/arathii23/finn-enam/releases/download/corpus-2026-11-03/finn-seed.tar.gz`

Verify that release is accessible and the deployed seed retains its genuine saved examples.
If it is missing, diagnose and preserve the intended main corpus; do not upload the QA database.

Important: dashboard environment variables override Docker defaults. Explicitly run the initial
hosted verification with `FINN_MODEL_PROVIDER=keyless`; preserve the stored provider secrets without
exposing or deleting them. New Groq/OpenRouter activation also needs a compatible explicitly selected
model, not a leftover paid provider model name. Do not enable a provider for tests just because an
old key happens to exist.

Wait for the actual build/deployment to finish; inspect failures and fix real blockers. Check the
public `/api/health` for keyless mode, healthy corpus and
`capabilities.current_source_research=true`. Confirm the new UI/assets are being served rather than
merely getting HTTP 200 from the previous release.

### 3. Verify the actual hosted investor journey

Use the public live app, with bounded requests and no paid model calls:

- Open the prepared replay, company data, genuine saved research and exact evidence.
- Choose Current filings, run one explicit seven-day check and inspect success/partial/failure
  states and timestamps. Keep legitimate validation failures visible. A failed source is not a
  quiet portfolio; do not weaken validation merely to display 15/15 green checks.
- Open a current notice and use Read & research filing. Confirm correct company/event binding,
  original attachment, document identity/publication and either usable evidence or a precise gap.
- Ask a focused current Infosys guidance question, inspect the exact passages and save the full
  cited context. Then inspect one non-demo symbol from another sector, within existing bounds.
  Do not hard-code this question, source URLs, periods or expected figures as answers.
- Verify unsupported-topic abstention, question follow-ups, loading/error states and saved-brief
  reuse. Opening a page must not silently launch research/model extraction.
- Save a point, add a note, reload, mark it done and export. Verify URLs, PDF pages, publication,
  evidence cutoff, speaker and hash survive; no user note is transmitted to a provider.
- Verify market dates/staleness, custom thresholds and missing data. Distinguish exchange evidence
  from the optional Yahoo market snapshot and never claim a filing caused a price move.
- Check phone widths and evidence-sheet focus/keyboard behavior. A real phone should open the final
  URL too; if no physical device is available, finish everything else and identify that owner check.

NSE may behave differently from Render's datacenter. Diagnose a failure rather than assuming local
success proves hosted access. Preserve a useful dated cached/replay path and accurate gaps. Do not
disguise cached documents as newly fetched or claim complete current coverage. If a free primary
source alternative is used, retain the same company/publication/citation discipline and verify it.

### 4. Publish GitHub Pages second

Prepare the final snapshot from the intended main/production seed, not the QA store, in keyless
mode. From the repository root, the export entry point is:

```bash
env FINN_MODEL_PROVIDER=keyless OPENAI_API_KEY='' ANTHROPIC_API_KEY='' \
  GEMINI_API_KEY='' GOOGLE_API_KEY='' GROQ_API_KEY='' OPENROUTER_API_KEY='' \
  PYTHONPATH=backend .venv/bin/python -m finn export-static
```

Then inside `frontend`, build to a separate directory so the live bundle is not overwritten:

```bash
VITE_STATIC=1 \
VITE_LIVE_APP_URL=https://finn-mow9.onrender.com \
VITE_LIVE_PRICES_URL=https://raw.githubusercontent.com/arathii23/finn-enam/live-data/live_prices.json \
npm run build -- --base=/finn-enam/ --outDir ../tmp/finn-pages-release
```

Inspect and publish through the **actual existing Pages configuration**. Keep the existing URL,
notebook storage origin, original PDF links, source hashes, genuine saved examples and replay cutoff.
Check public assets, deep links and navigation after deployment. In the static demo, a new question
or event must link to the deployed live app with its context intact; no static-mode write-error loop.

The existing live-data branch/workflow is separate from Pages. Verify its latest successful run,
actual fetched/session dates and failure metadata; trigger one normal run if needed. Keep its data
separate from the seeded replay. A five-minute cron is best-effort, not a real-time service guarantee.

### 5. Optional free AI verification — without delaying the working keyless release

Use `docs/FREE_RESOURCES.md` and check current official provider documentation if model availability,
quota or terms have changed. The adapters were tested offline; real keys/quality were not tested.

- If the user already has an appropriate server-side free-plan key and clearly authorizes its use,
  perform a minimal bounded test and review its answer against the exact source pages. An accepted
  JSON schema is not proof of faithful financial reasoning or complete conditions.
- Never borrow Claude Code/ChatGPT credentials, expose keys in `VITE_*`, buy credits, upgrade a plan,
  create accounts accepting terms, rotate accounts to evade quotas, or fall back to a paid model.
- Groq free eligibility is account-level; the key string alone does not establish it. OpenRouter
  must retain the free model allowlist, zero-price and data-policy guards.
- If no suitable key is available, leave keyless active, show the precise owner setup steps and
  mark real-key validation pending. Publication should still finish.

### 6. Remaining practical and documentation work

Fix any concrete defects found in the above journeys. Prioritize source integrity, relevance,
readability, useful next actions, graceful failures and fast phone use. Do not turn the optional
reference-menu examples into a full brokerage, real-time trading terminal or large rewrite.

Retain honest boundaries: the prepared Review universe is 15 holdings; thresholds are in-app flags,
not delivered notifications; quarterly caches have 3/3/3/2 verified metrics for the prepared examples;
INFY has verified YoY but no verified QoQ; undisclosed EBITDA is omitted. Guidance comparisons are
conservative, with pending outcomes and incomplete history, not a complete four-quarter scorecard.
Do not invent values, comparative periods, management backgrounds, user feedback or adoption metrics.

Record the hosted restart/cold-start behavior and actual resource/source limits. Render's ephemeral
store does not guarantee persistence of newly created jobs/current checks after redeploy. The seed
restores genuine saved demonstrations, and the browser notebook has its own persistence/export.
Do not promise durable server-side history that the free setup does not provide.

Update `BUILD_STATUS.md`, the current deployment instructions, the email-claim matrix and
`docs/BUILD_HISTORY.md` with actual dates, commits, URLs and checks. Preserve historical entries.
Do not modify the already-sent email or send a new message to ENAM.

The existing local build-history PDF is `output/pdf/FINN_AI_Build_History.pdf`. Preserve it; it
predates this continuation and is not automatically the same file as the email screenshot's
`FINN_AI_Build_History_Complete.pdf`. If an updated history supplement is needed, use only authentic
chat exports/records available to you, label its date/scope, and render/check the PDF. Never invent
missing conversations or call a narrative summary an authentic transcript. Do not publish private
chat PDFs to the public repository or replace an existing submission attachment automatically.

## Completion standard and final report

End with a concise factual report containing:

1. Both unchanged public URLs and the published source/static revisions.
2. What was implemented/fixed in this Claude continuation.
3. Actual local and public checks, including a saved-evidence/notebook journey and hosted source
   outcome. Separate partial checks and physical-device limitations from passed checks.
4. Active provider mode, free-resource boundary and any precise optional key/user action remaining,
   without exposing secrets. No new charges or submission should have occurred.
5. Current limitations, rollback reference and updated documentation/evidence locations.

Do not claim the update is live before verifying both public destinations. If one platform truly
blocks completion, finish the other independent work, retain the prepared release, and report the
exact blocker and minimum user action. Do not repeatedly ask for permission for the already-approved
publication, and do not claim an unavailable physical device or model account was tested.
