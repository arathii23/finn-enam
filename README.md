# FINN — primary-source company research (Milestone 1)

FINN helps an investor understand a listed company or exchange event from primary sources (NSE records, annual reports, earnings-call transcripts) and leave with one useful follow-up question. Milestone 1 is one connected path: **INFY → real NSE/company sources → page-located passages → bounded research view → mobile evidence inspection**, in a dated historical replay.

Requirements: `1. ENAM_AI_Engineer_Build_Challenge_Main.pdf`, `2. ENAM_AI_Engineer_Build_Challenge_Reference.pdf`. Scope decisions: `FINN_Prebuild_Specification.md`. Current state and test evidence: **`BUILD_STATUS.md`**.

## Run it (macOS/Linux, internet required for ingestion)

```bash
cd ENAM_Holdings
bash scripts/m1_verify.sh          # venv + deps, tests, Vite build, INFY ingestion, checks, startup smoke
. .venv/bin/activate && cd backend
python -m finn serve               # http://127.0.0.1:8000
python -m finn serve --host 0.0.0.0  # to open from a phone on the same Wi-Fi: http://<mac-LAN-IP>:8000
```

Model generation: create a local `.env` in this project root with `ANTHROPIC_API_KEY=...` and `FINN_MODEL_PROVIDER=anthropic`. The app parses this ignored file automatically; do not paste the key into chat or commit it. Claude defaults to `claude-haiku-5-5`, with one optional `claude-sonnet-5-5` escalation. OpenAI remains available by choosing `FINN_MODEL_PROVIDER=openai`, setting `OPENAI_API_KEY`, and selecting the GPT models in `.env.example`. Runtime API billing is separate from coding subscriptions. Without the selected provider's key, research completes as **Partial**: identity, eligible documents, ranked passages and coverage gaps are shown; no prose is generated and nothing is filled from model memory.

Local verification on 30 October selected **`claude-sonnet-5-5` at low effort** for research: the cheaper model mishandled qualifications in inspected INFY responses. The private local configuration overrides the adapter's starting default and disables escalation. This is an initial source audit, not the full ten-packet model evaluation. After the user authorised using the available credits, the local development limit was raised from $0.10 to **$5 total, $0.25 per job**. Budget/provider failures offer an explicit retry; completed jobs remain deduplicated. Existing saved results and evidence remain readable without generating new prose. Credit expiry still prevents new research unless funded API access is available. See `BUILD_STATUS.md` and `docs/NEXT_STEPS.md` for the remaining gates.

Individual commands (from `backend/`): `python -m finn check-runtime` · `python -m finn ingest INFY` · `python -m finn verify --symbol INFY` · `python -m pytest -q tests` · `python tests/ui_check.py ../frontend/dist /tmp/ui` (Playwright UI check). Frontend dev server: `cd frontend && npm install && npm run dev` (proxies `/api` to :8000).


## Two workflows (mobile)

- **Review (Push):** `#/` — a prioritised digest across the 15-company portfolio (`manifests/portfolio.json`).
  Leading/notable/routine tiers from a deterministic classifier (`backend/finn/prioritize.py`), collapsed
  routine filings, configurable EOD price/volume anomaly flags, and event → research links. Holdings with no
  ingested data are shown honestly as "not yet ingested".
- **Research (Pull):** `#/research` or any `#/c/<SYMBOL>` — primary-source company research with per-claim
  evidence you can open at the exact PDF page.

Populate the full portfolio on a networked machine:
```bash
cd backend && python -m finn ingest HCLTECH RELIANCE ICICIBANK BHARTIARTL LT MARUTI HINDUNILVR SUNPHARMA ULTRACEMCO TITAN TRENT ASTRAL
```
INFY, CERA and HDFCBANK are already ingested. Rebuild the UI with `cd frontend && npm install && npm run build`.


## Architecture

```
NSE EQUITY_L.csv ─┐
NSE daily files ──┼─> guarded fetcher (https-only, size cap, byte validation, every attempt logged)
NSE announcements ┤        │
AR / transcripts ─┘        v
              content-addressed files (sha256) + SQLite metadata + FTS5 passages (PDF page index, speaker)
                           │
              replay cutoff filter (proven exchange publication time ≤ cutoff)  ← before retrieval
                           │
              bounded retrieval (AR context / transcript commentary / event filing, separately)
                           │
              model (Anthropic Messages / OpenAI Responses, JSON schema) → citation + number validation   [optional]
                           │
              FastAPI (same origin) ── React/Vite mobile UI: company/event → research → evidence sheet → PDF
```

- `backend/finn/sources/` — `fetch.py` (guarded retrieval), `nse.py` (identity, EOD, announcements, annual-report index), `documents.py` (identification, availability proof, page extraction).
- `backend/finn/replay.py` — manifest + publication-cutoff filter. `retrieval.py` — FTS5 per section. `research.py` — packet, model call, validation, gaps. `llm.py` — Responses adapter + cost ledger. `service.py` — jobs and read models. `api.py` — HTTP routes. `verify.py` — real-data checks.
- `manifests/replay_2025_04.json` — replay source **metadata only** (URLs, doc types, periods, where to search for publication evidence). No answers, values or verdicts.
- `Dockerfile`, `render.yaml` — single-service deployment design; **not built or deployed**.

## Evidence rules in code

- Publication time comes from a dated exchange record whose attachment is that exact file; call dates, filenames and cover dates are never treated as proof. Date-only proof is treated as available at 23:59:59 IST that day. Unproven documents are excluded from replay.
- Identity checks are generic (legal name, document-type terms, fiscal-period spellings on the first pages).
- Generated statements are dropped unless cited ids belong to the evidence packet, the expected document type is cited, financial numeric tokens appear in cited text, and supplied speaker attribution matches the cited passages. An exact reporting-period label can come from document metadata; its digits cannot support an unrelated financial value.
- Citation membership and whole-number-token checks do not establish semantic entailment or financial comparability. Generated research still requires source-level manual evaluation before any accuracy claim.
- Source text is delimited and escaped as data; the prompt forbids following embedded instructions.
