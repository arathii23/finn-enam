# Build history (authentic AI conversations)

The assessment requires the actual coding conversations, not a reconstruction. Preserve them by export or share link; do not paraphrase them into this file.

| Phase | Tool / surface | Where the authentic record lives |
|---|---|---|
| Feasibility review, source audit, pre-build specification | (planning conversations) | Export/share links to be added by the builder |
| Milestone 1 implementation (30 Oct 2026) | Claude (claude.ai project "Enam holdings", Claude Code session) | https://claude.ai/code/session_01S6ppkkVG3jJnpe7wRd4FGQ — create a share link and verify an evaluator can open it |

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
