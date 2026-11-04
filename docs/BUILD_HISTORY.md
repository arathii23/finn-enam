# Build history (authentic AI conversations)

The assessment requires the actual coding conversations, not a reconstruction. Preserve them by export or share link; do not paraphrase them into this file.

| Phase | Tool / surface | Where the authentic record lives |
|---|---|---|
| Feasibility review, source audit, pre-build specification | (planning conversations) | Export/share links to be added by the builder |
| Milestone 1 implementation (30 Oct 2026) | Claude (claude.ai project "Enam holdings", Claude Code session) | https://claude.ai/code/session_01S6ppkkVG3jJnpe7wRd4FGQ — create a share link and verify an evaluator can open it |
| M3 management profiles + M4 local polish (31 Oct 2026) | Codex desktop, this chat | Authentic chat must be exported/shared and evaluator access checked; no share link fabricated |
| Financial trust/workflow pass and keyless Claude Code handoff (3 Nov 2026) | Codex desktop, this chat | Preserve the authentic chat; detailed continuation instructions are in `HANDOFF_CLAUDE_CODE.md`, not a replacement conversation export |
| Post-submission practical workflow improvements (4 Nov 2026) | Codex desktop, this chat | Preserve this authentic continuation; `POST_SUBMISSION_IMPROVEMENTS.md` records changes and checks, not a substitute conversation export |

4 November supplementary status: the user reports the assessment already submitted. Work in this
continuation improves the local app and keeps the submitted links unchanged until a later publish.
Current filing metadata checks, current-source research, a browser-local cited notebook, practical
static-to-live handoffs, question/quotation fidelity and optional Groq/free-only OpenRouter adapters
were implemented. A real current NSE run retained 49 valid notices, with 14/15 holding checks fully
validated; one holding's partial check remains visible. Current Infosys research exposed and repaired
standalone-speaker/bundled-title transcript discovery. Tests use fictional fixtures; separate real
source checks use a copied corpus and keys disabled. Verification scope and limits are recorded in
`POST_SUBMISSION_IMPROVEMENTS.md`. No new model account/key, model API spend, commit, push, hosted
deployment or submission was made in this continuation. Earlier entries retain their historical scope.

3 November supplementary status: 119 backend tests and the frontend build passed; corrected keyless
cold source checks and local read-only restart evidence are retained in ignored verification data.
One user-requested minimal API access probe was rejected for insufficient credits, with no purchase
or recharge. The next build must work without a model API key. Nothing was committed, pushed,
publicly deployed or submitted. Earlier dated measurements below retain their original scope.

Notable decisions recorded in that M1 conversation (supplementary only):
- Build environment could not reach NSE/OpenAI/PyPI/npm; retrieval was implemented and tested against a mocked network with synthetic fixtures, and a single script runs real ingestion on the builder's Mac.
- FastAPI and Vite could not be installed in the build environment; the service layer was tested directly and the UI via Playwright, with FastAPI startup deferred to the Mac verification script.
- Publication availability must come from a dated exchange record listing the exact attachment; otherwise the document is excluded from replay.

## Local verification and Claude integration — 30 October 2026

The authentic Codex conversation for this work must also be exported/shared and its access checked before submission. No public conversation link has been fabricated here.

Supplementary record (not a substitute for that conversation): real NSE ingestion and FastAPI startup were exercised; date-mismatched EOD responses and standalone speaker labels were repaired; Anthropic Messages support and local ignored configuration were added. Four Haiku requests and one Sonnet request were made under a $0.10 total test cap. Manual inspection caught a borrowed qualifier in one Haiku draft and misleading gap/rate language in another. A same-packet Sonnet response preserved the relevant qualifications. Raw output snapshots and the source-level review are in `data/verification/`; this directory is ignored by Git and must be packaged deliberately if needed for review.

The initial environment's network restriction did not establish that the user's Mac lacked internet access. The later normal-network checks retrieved real sources successfully. The complete model evaluation, hosted retrieval and physical-phone checks remain outstanding.

## Budget recovery and evaluation continuity — 30 October 2026

The user reported a spending-limit screen, authorised using available API credits and clarified that the credits expire in two days. The local app limit was increased from $0.10 to $5 total/$0.25 per job; no provider credits were purchased. A recoverable partial request can now be explicitly retried while completed/in-flight work remains deduplicated. The same blocked request was retried through the browser and completed; its subsequent reuse made no additional model call. Current suite: 25 passing tests, TypeScript/Vite build passed. This is part of the authentic Codex conversation that must be preserved. `NEXT_STEPS.md` separates persisted demonstrations from the funded API access needed for new evaluator questions.

## Source-audit repairs (v1.8) and portfolio queue — 31 October 2026

Claude Code (Opus) session continuing the handoff. Work ran in a Linux cloud workspace against a copy of
the real `data/finn.sqlite3` (this session's shells could not reach NSE/PyPI; the earlier macOS venv was
not runnable here). Model calls used the live Anthropic API with the user's key.

- Fixed the four outstanding source-audit findings via evidence selection + validation (not answer edits):
  same-speaker neighbour-context retrieval (HDFCBANK LDR/"90 mark"), standalone-basis discipline (CERA),
  a fiscal-token validator false-positive, and a period-consistency check. Regenerated INFY/CERA/HDFCBANK
  on Sonnet and re-audited at source, rendering two contested PDF pages.
- Built the portfolio review queue (Push): `prioritize.py`, `GET /api/portfolio`, a mobile Review tab.
- 49 Python tests pass (incl. 3 new repair regressions + 6 queue/anomaly tests); 30/30 Playwright queue UI
  checks at 360/390/430 px. API usage this session: 9 Sonnet calls, $0.23 (list price); cumulative $0.78.

The authentic conversation for this session must be exported/shared and its reviewer access verified before
submission; no public link is fabricated here.

## M1 completion + M2 Numbers vs Narrative — 31 October 2026 (Opus 4.8, networked Mac)

Claude Code (Opus 4.8) session on the user's networked Mac; venv runnable, NSE reachable.

- **M1:** ingested the remaining 12 holdings from real NSE sources (EOD + announcements + results/press
  PDFs), backfilled EOD for HDFCBANK/CERA. All 15 holdings now carry 9 EOD days + announcements; results
  PDFs parsed for 12/15 (LT/TITAN/ASTRAL have no in-window results attachment — shown as a gap). Review
  queue: 15 checked, 55 leading + 23 notable events, 2 anomalies. Ingestion made **no model calls**.
- **M2:** built the deterministic Numbers-vs-Narrative engine (`finn/compare.py`) + API + mobile view.
  INFY FY25 revenue growth 4.5–5% CC guided vs 4.2% delivered = −0.3pp below, with acquisition caveat and
  cross-basis note; margin 21.1% within 20–22%; FY26 outcome pending. Comparability gate enforced; honest
  degradation on HDFCBANK (0) and CERA (1). **No model call — zero API spend.**
- Hardened `config.py` against a leaked host-only `ANTHROPIC_BASE_URL`. Checks: 60 Python tests pass;
  `npm run build` passes; view exercised in-browser at 360/375px with evidence sheet opening to exact PDF
  pages. Cumulative ledger unchanged at $0.783512.

## M3 management profiles + M4 local polish — 31 October 2026 (Codex desktop)

Supplementary implementation/verification record, not a reconstruction of the conversation:

- Read both assignment briefs, the pasted handoffs, current changes, and real stored appointment
  filings. Built a conservative, ticker-independent deterministic extractor and company-page cards.
  HDFCBANK's inclusion in senior management is distinguished from a new hire; CERA's appointment
  profile is quoted from its filing. Both predate the digest window and are explicitly labelled.
- Corrected dividend/director-mention and auditor-appointment classification false positives.
  Added API company/attachment/cutoff/window gates and source/abstention regressions.
- Polished persistent navigation, heading wrapping, quarterly units/citations, zero threshold inputs,
  review-state fingerprints and evidence-sheet keyboard/scroll behaviour. Completed unreadable
  quarterly results are now cached to prevent repeated automatic spend.
- Baseline 66 tests; final **86 passed**, with a dependency deprecation warning; official frontend
  build passed. **21 real-app browser layout checks** across seven views at 360/390/430 CSS px.
  Evidence page links, keyboard behaviour, threshold Apply and reviewed Undo were exercised.
  Existing quarterly/research outputs were read from saved data. This was not a physical-phone,
  container, hosted-source or complete independent model audit.
- Measured ledger delta **1 automatic quarterly attempt, $0.000659** during the initial visit to the
  old server. Total **104 calls, $0.7947052**. Management/tests/later browser checks made no model
  calls. Updated config/example/un-applied hosting proposal to agree on $5/$0.25 caps and the
  selected research model. No commit, push, public deployment, purchase or submission.

Source-bound deterministic output snapshots live in ignored `data/verification/m3_management_*.json`;
browser screenshots/layout observations are in `docs/m3_m4_ui_check/`. Preserve the actual Codex chat,
all prior Claude records and the ignored source corpus for the eventual submission package.
