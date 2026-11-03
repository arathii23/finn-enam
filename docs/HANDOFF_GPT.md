# FINN — build handoff prompt (for GPT‑6.1 Sol, extra‑high)

> Superseded for continuation, 3 November 2026: read [HANDOFF_CLAUDE_CODE.md](HANDOFF_CLAUDE_CODE.md)
> and the latest `BUILD_STATUS.md` entry. The user confirmed an extension and now requires a useful
> keyless submission. API generation was rejected for insufficient credits; 119 tests and the latest
> frontend build pass. No local server remains running. The old task list and API assumptions below
> are retained as history, not current instructions.

> Continuation update — 31 October 2026: M3 management profiles and the M4 local pass are
> complete. Read the latest entry in `BUILD_STATUS.md` and `docs/SUBMISSION_CHECKLIST.md`
> before using the original handoff below. 86 tests, official frontend build and 21 browser
> layout checks passed. Ledger: $0.7947052. Nothing committed, pushed, deployed or sent;
> M5 still requires explicit approval. The local server is at 127.0.0.1:8000; inspect its
> listener before restarting. Preserve all working-tree changes and ignored source data.

Paste this to the next coding agent. It assumes filesystem access to this project and GitHub access.

---

You are continuing an in‑flight build of **FINN**, a mobile‑first primary‑source investor
research prototype, for the ENAM Holdings "AI Engineer Build Challenge." A previous coding
agent (Claude) built M1, M2, and most of M3. Your job is to **finish M3, do the M4
design/polish pass, and prepare M5 (ship)** — without breaking what works.

- **Project root:** `/Users/aadityarathi/Downloads/ENAM_Holdings`
- **Deadline:** 1 November 2026. **GitHub target:** github.com/arathii23
- **Goal:** a standout submission — complete, reliable, beautiful mobile demo with genuine
  product judgment. "Thin‑but‑working beats broad‑but‑broken; a demo that doesn't run is the
  worst outcome." **No AI slop.**

## FIRST: orient (don't skip)
1. The two assignment PDFs (authoritative): `1. ENAM_AI_Engineer_Build_Challenge_Main.pdf`
   and `2. ...Reference.pdf`. Extract text with pypdf (poppler isn't installed):
   `cd backend && . ../.venv/bin/activate && python -c "from pypdf import PdfReader; [print(p.extract_text()) for p in PdfReader('../1. ENAM_AI_Engineer_Build_Challenge_Main.pdf').pages]"`
2. `BUILD_STATUS.md` (top two dated sections = M1 + M2) and `docs/BUILD_HISTORY.md`.
3. Skim `backend/finn/{compare.py, quarterly.py, research.py, service.py, api.py,
   prioritize.py, discovery.py, config.py}` and `frontend/src/{NarrativeView.tsx,
   CompanyView.tsx, ResearchView.tsx, QueueView.tsx, api.ts, ui.tsx, styles.css}`.
4. Run `git status` and `git diff --stat` — **nothing from this session is committed yet**;
   all M1/M2/M3 changes are in the working tree, and new rows are in `data/finn.sqlite3`
   (git‑ignored). Do not commit or push without explicit user approval (see constraints).

## HARD CONSTRAINTS (do not violate)
- **PULL / research uses PRIMARY sources only** (annual reports, transcripts, exchange
  filings). No news, broker notes, Screener summaries, or model memory. **PUSH‑side
  enrichment** (e.g. a person's bio) may use outside sources, but only **clearly labelled**.
- Keep the **validation layer** intact: a claim/number is dropped unless every cited id is in
  the packet, numbers appear **verbatim** in the cited text, reporting basis
  (standalone/consolidated) and currency basis (constant‑currency vs reported) are preserved,
  and speaker/period match. **Never fabricate. "Omit rather than guess."**
- **Budget: $5 total / $0.25 per job.** Cumulative ledger ≈ **$0.794**
  (`sqlite3 data/finn.sqlite3 "select sum(actual_usd) from model_calls"`). Credits expire
  ~1 Nov. Do **not** raise caps. Spend deliberately on durable, audited, **cached** demos only.
- **Do not** deploy publicly, create paid resources, buy credits, push to GitHub, or send the
  submission **without the user's explicit approval for each**. Keep the key in the git‑ignored
  `.env`. Inspect running processes before starting a server. Preserve existing files and the
  authentic Claude Code conversation/history.
- The engine must **generalise to any NSE ticker** where data exists — no ticker‑specific logic.

## Environment / how to run
- venv (macOS, runnable here): `. .venv/bin/activate`. Run backend cmds from `backend/`.
- **CRITICAL:** the shell exports `ANTHROPIC_BASE_URL=https://api.anthropic.com` (a proxy var
  that drops `/v1`). `config.py:_anthropic_base_url()` now repairs it, but also prefix model/
  test commands with `env -u ANTHROPIC_BASE_URL` as belt‑and‑suspenders.
- Tests (data‑only, no spend): `cd backend && env -u ANTHROPIC_BASE_URL OPENAI_API_KEY=''
  ANTHROPIC_API_KEY='' python -m pytest -q tests` → currently 60+ pass.
- Frontend build: `cd frontend && npm run build` (tsc + vite; node 26 / npm 11).
- Server: `cd backend && env -u ANTHROPIC_BASE_URL python -m finn serve --host 127.0.0.1
  --port 8000`. A server may already be running — check `lsof -nP -iTCP:8000 -sTCP:LISTEN`.
  Restart after backend changes. The SPA caches index.html — cache‑bust in the browser with a
  `?v=N` query to force the new JS bundle.
- Model: provider anthropic, primary `claude-sonnet-5-5` (research reasoning), escalation off.
  Use `claude-haiku-5-5` for cheap **bulk extraction** (verified working, ~$0.00003/tiny call).
  Routing philosophy already established: Haiku for extraction, Sonnet for research reasoning,
  deterministic Python for all arithmetic/judgment.
- `data/finn.sqlite3` + `data/` are git‑ignored. The `derived_cache` table caches quarterly
  results so they serve with zero re‑spend.
- Git attribution used so far was Claude's; you are a different agent, so do **not** claim
  Claude co‑authorship. Use neutral commit messages. (No commits without approval anyway.)

## What's already done & verified
**M1** — all 15 holdings populated from real NSE (EOD 9 days each; announcements; results PDFs
for 12/15; LT/TITAN/ASTRAL have no in‑window results attachment — shown as a gap). Review
queue (`App.portfolio_queue` / `GET /api/portfolio`) shows 55 leading + 23 notable events, 2
anomalies. 49→60 tests green; npm build passes. Zero model spend.

**M2** — "Numbers vs Narrative" (promised vs delivered), **deterministic, zero model spend**:
- `backend/finn/compare.py` (management‑speaker‑only extraction, comparability gate on
  metric/year/currency‑basis/entity, verbatim number check, deterministic arithmetic,
  source‑cited acquisition caveat + cross‑basis note). Tests: `backend/tests/test_compare.py`
  (11). Service: `App.narrative_numbers`. API: `GET /api/companies/{symbol}/narrative`.
  Frontend: `frontend/src/NarrativeView.tsx`, route `#/c/<SYM>/narrative`, entry button in
  CompanyView, CSS under "Numbers vs Narrative" in styles.css. **No red/green** — a calm value
  band shows position. Verified in‑browser at 360/375px; evidence sheet opens to the exact PDF
  page with publication proof + content hash.
- INFY result (hero demo): revenue growth FY25 guided 4.5–5% CC vs delivered 4.2% = **0.3pp
  below range** (+ in‑tech acquisition caveat + 6.1% reported cross‑basis note); margin 21.1%
  within 20–22%; FY26 revenue & margin "outcome pending." HDFCBANK → 0 items; CERA → 1 item
  (FY26 ~20% aspiration, pending). Honest generalisation, no ticker‑specific logic.

**M3 quarterly first‑cut** — DONE (Haiku bulk extraction + deterministic validation, cached):
- `backend/finn/quarterly.py` (`select_pnl_passages` with same‑page‑sibling grouping;
  `EXTRACT_SCHEMA` = all plain‑string fields with `""` = absent, because structured‑output
  caps nullable params at 16; `validate_and_compute`: verbatim check, date‑plausibility gate
  for QoQ/YoY, parentheses=negative, EBITDA only if explicitly labelled). Tests:
  `backend/tests/test_quarterly.py` (6). `derived_cache` table added in `backend/finn/db.py`.
  Service: `App.quarterly_results` + `_extract_quarterly` (model `claude-haiku-5-5`,
  `max_output_tokens=2200`). API: `GET /api/companies/{symbol}/quarterly`. Frontend:
  `QuarterlyCard` in CompanyView.tsx (rendered when `hasNarrative`) + CSS. Verified in‑browser.
- Cached working: **INFY, HCLTECH, ULTRACEMCO** (full Rev/PBT/PAT); **HINDUNILVR** (PBT/PAT).
  Honestly omitted: ICICIBANK/HDFCBANK (bank/no filing), RELIANCE (complex), BHARTIARTL/
  SUNPHARMA/TRENT/MARUTI (press‑release/garbled). EBITDA omitted everywhere (not in statutory
  statements). Spot‑checked HCLTECH numbers correct; QoQ/YoY exact. M3‑quarterly spend ~$0.01.

## Where we stopped — FINISH THIS FIRST: M3 management‑change card
The brief's second "example we love": a management‑change push item that doesn't just say
"CFO resigned" but gives a short background of the incoming person. The correct, slop‑free
approach is to ground the bio in the **primary appointment filing** (SEBI Reg‑30 letters
include a mandated "Brief Profile"), **not model memory**.

Already fetched into the corpus (`data/finn.sqlite3`) as exchange_filing docs:
- HDFCBANK appointment letter (version id starts `ver_9a441d21`): **Mr. Sanjay D'Souza**, Group
  Head – Emerging & Informal Micro Enterprises Group, Senior Management, appointed 8 Apr 2025.
  Annexure‑I profile present (joined HDFC Bank 1 Dec 1999, ~25 yrs, Retail/Wholesale Credit &
  Emerging Enterprises, heading EEG since Oct 2016, etc.).
- CERA appointment letter (version id starts `ver_7f0b070b`): **Mr. Ramesh Baliga**, Chief
  Business Officer – Polymers & Emerging Business India, w.e.f. 24 Feb 2025. Annexure‑I profile
  present (B.Tech Mechanical, 38+ yrs, Jaquar/Watertec/Acquaviva, etc.).

Use `link_announcement_attachment` in `backend/finn/sources/documents.py` as the pattern to
fetch more appointment letters for other genuine "Appointment of Mr/Ms X" announcements (e.g.
RELIANCE — its subject is truncated, so the name is in the letter).

**To do for management‑change:**
1. Build extraction (new module, e.g. `backend/finn/management.py`). For a management_change
   announcement whose attachment is a fetched appointment letter, extract {appointee name,
   role, effective date, brief profile} **from the filing**. The profile sits under a literal
   "Brief Profile:" / "Annexure I" header, so a conservative deterministic parse is viable; or
   use a cheap Haiku call, but **validate**: name/role must appear verbatim in the cited
   passage, and show the profile text quoted from the filing with an evidence link. Label it
   "from the appointment filing" (primary). Optionally add a clearly‑labelled, visibly separate
   "background (model knowledge, may be out of date)" line — but primary‑only is safer.
2. **Event selection:** `prioritize.py` currently over‑classifies some dividend/record‑date/
   auditor announcements as management_change (false positives). Either tighten the classifier
   or make the card trigger only on genuine appointment subjects (regex like
   `Appointment of (Mr|Ms|Dr|Mrs)\.? <Name> as <role>`) with a named person. Never show a
   "management change" card for a dividend. Add/adjust tests.
3. Service method + API route (mirror the quarterly/narrative pattern; cache if you use a
   model). Frontend card — put it where the user meets the event: inline in QueueView for
   companies whose leading events include a management change, or on CompanyView. Dense, calm,
   with an evidence link to the filing PDF.
4. Tests (verbatim validation, false‑positive rejection), then `npm run build`, then verify
   in‑browser at 360–430px. Update BUILD_STATUS.md + docs/BUILD_HISTORY.md with **only verified
   facts and measured spend**. Report what actually ran.

## Then: M4 — interaction + design pass (make it feel like a product)
- Cohesion across Review (queue) / Research / Numbers‑vs‑Narrative / Quarterly /
  Management‑change so they read as one product, not separate templates.
- Distinctive, dense, calm, high‑contrast mobile. Evidence always one tap away (pattern via
  EvidenceSheet). **No red/green investment verdicts** anywhere. Smooth state transitions.
  Real phone test at 360–430px; no horizontal overflow; ≥44px touch targets.
- Light‑mode‑only today; consider a careful dark mode only if time permits and it won't risk
  breakage. Don't sprawl.
- Re‑run full test suite + npm build. Update docs. Report.

## Then: M5 — ship (ONLY on the user's explicit, step‑by‑step go‑ahead)
Do nothing here until the user says so, each step: deploy per `docs/DEPLOYMENT.md` →
phone‑test the hosted URL → restart/persistence check → push repo to github.com/arathii23 →
finalise `docs/COVERING_EMAIL_DRAFT.md` → export the authentic AI‑conversation share links.
Confirm before each outward/irreversible action.

## Reporting discipline (every milestone)
Report: what changed; which checks **actually** ran and their results; measured API spend;
remaining gaps; and whether each result is real (freshly computed) or cached/saved. Update
BUILD_STATUS.md and docs/BUILD_HISTORY.md with verified facts only. Never describe an unrun
check as passed. When unsure between adding breadth vs. polishing, choose polish — a focused,
reliable, beautiful demo wins.
