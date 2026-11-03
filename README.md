# FINN — primary-source investor research

FINN combines a prioritised 15-company review queue with primary-source company research, a
guidance-versus-outcome comparison, quarterly headline tables and appointment profiles. Claims
link to the exact evidence passage and PDF page. The demo is a labelled historical replay with
an evidence cutoff of 30 April 2025; unavailable data remains an explicit gap.

Requirements: `1. ENAM_AI_Engineer_Build_Challenge_Main.pdf`, `2. ENAM_AI_Engineer_Build_Challenge_Reference.pdf`. Scope decisions: `FINN_Prebuild_Specification.md`. Current state and test evidence: **`BUILD_STATUS.md`**.

## Run it (macOS/Linux, internet required for ingestion)

```bash
cd ENAM_Holdings
bash scripts/m1_verify.sh          # venv + deps, tests, Vite build, INFY ingestion, checks, startup smoke
. .venv/bin/activate && cd backend
python -m finn serve               # http://127.0.0.1:8000
python -m finn serve --host 0.0.0.0  # to open from a phone on the same Wi-Fi: http://<mac-LAN-IP>:8000
```

**Free by default (no key, nothing to spend).** With no model key set, FINN runs fully keyless:
the Push digest, saved research briefs, quarterly tables, management cards, narrative-vs-numbers
and — for a fresh question — a **verbatim extractive source brief** that quotes the sentences most
relevant to your question from the primary sources and cites each one (`backend/finn/brief.py`).
Figures are quoted, never computed; nothing is filled from model memory. This is the shipped
submission configuration, so the evaluator needs no key.

**Optional genuine AI synthesis, also free.** Get a free Google AI Studio key
(https://aistudio.google.com/apikey — no billing) and set `FINN_MODEL_PROVIDER=gemini` with
`GEMINI_API_KEY=...` in a local `.env`. On-demand research then runs through `gemini-2.0-flash` at
zero per-token cost, through the same citation/number/speaker validation gates; a free-tier rate
limit degrades gracefully to the keyless source brief. Paid providers (`anthropic`, `openai`)
remain selectable but are never required. See `.env.example`. Budget ceilings: **$5 total, $0.25
per job** (list-price reservations; the free tier reserves $0).

**Put it on a phone — free, no sleep.** Build a static snapshot and publish it to any free CDN,
plus a QR code. See **`docs/DEPLOY_FREE.md`**.

Individual commands (from `backend/`): `python -m finn check-runtime` · `python -m finn ingest INFY` · `python -m finn verify --symbol INFY` · `python -m pytest -q tests` · `python tests/ui_check.py ../frontend/dist /tmp/ui` (Playwright UI check). Frontend dev server: `cd frontend && npm install && npm run dev` (proxies `/api` to :8000).


## Two workflows (mobile)

- **Review (Push):** `#/` — a prioritised digest across the 15-company portfolio (`manifests/portfolio.json`).
  Leading/notable/routine tiers from a deterministic classifier (`backend/finn/prioritize.py`), collapsed
  routine filings, configurable EOD price/volume anomaly flags, and event → research links. Holdings with no
  ingested data are shown honestly as "not yet ingested". An optional **Live market snapshot** card pulls
  free real-time EOD from Yahoo Finance (no key) and applies the same anomaly flags — clearly separated from
  the verified replay (`backend/finn/sources/live_eod.py`, `GET /api/live-prices`, `python -m finn live-prices`).
- **Research (Pull):** `#/research` or any `#/c/<SYMBOL>` — primary-source company research with per-claim
  evidence you can open at the exact PDF page.
- **Numbers vs Narrative:** `#/c/INFY/narrative` — deterministic guidance/outcome comparisons with
  metric, year, entity and currency-basis gates; unmatched outcomes remain pending.
- **Company context:** `#/c/INFY` has a saved quarterly table; `#/c/HDFCBANK` and `#/c/CERA` have
  source-quoted management profiles with separate appointment/profile evidence. These two filings
  predate the digest window and are labelled accordingly.

Populate the full portfolio on a networked machine:
```bash
cd backend && python -m finn ingest HCLTECH RELIANCE ICICIBANK BHARTIARTL LT MARUTI HINDUNILVR SUNPHARMA ULTRACEMCO TITAN TRENT ASTRAL
```
All 15 holdings are populated in the current local database. Rebuild the UI with
`cd frontend && npm install && npm run build`. Data and source PDFs are git-ignored: a fresh checkout
needs ingestion or an intentionally seeded copy of `data/`. Saved research can be read without a
model call; new summaries require configured API access. See `BUILD_STATUS.md` for verified coverage.


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
     keyless: verbatim extractive source brief (brief.py)   ─OR─   optional model (Gemini free /
              Anthropic / OpenAI, JSON schema) → citation + number + speaker validation
                           │
              FastAPI (same origin) ── React/Vite mobile UI: company/event → research → evidence sheet → PDF
                           │
              static export (snapshot.py) ──> CDN-hosted read-only snapshot (no backend, never sleeps)
```

- `backend/finn/sources/` — `fetch.py` (guarded retrieval), `nse.py` (identity, EOD, announcements, annual-report index), `documents.py` (identification, availability proof, page extraction).
- `backend/finn/replay.py` — manifest + publication-cutoff filter. `retrieval.py` — FTS5 per section. `research.py` — packet, model call, validation, gaps. `llm.py` — Responses adapter + cost ledger. `service.py` — jobs and read models. `api.py` — HTTP routes. `verify.py` — real-data checks.
- `backend/finn/brief.py` — keyless extractive source brief (verbatim quote selection, no model). `snapshot.py` — static read-model export. `backend/finn/llm.py` — Gemini / Anthropic / OpenAI adapters + cost ledger.
- `manifests/replay_2025_04.json` — replay source **metadata only** (URLs, doc types, periods, where to search for publication evidence). No answers, values or verdicts.
- `Dockerfile`, `render.yaml` — single-service deployment design (keyless/Gemini default). `scripts/make_qr.py` — QR + share card. See `docs/DEPLOY_FREE.md`.

## Evidence rules in code

- Publication time comes from a dated exchange record whose attachment is that exact file; call dates, filenames and cover dates are never treated as proof. Date-only proof is treated as available at 23:59:59 IST that day. Unproven documents are excluded from replay.
- Identity checks are generic (legal name, document-type terms, fiscal-period spellings on the first pages).
- Generated statements are dropped unless cited ids belong to the evidence packet, the expected document type is cited, financial numeric tokens appear in cited text, and supplied speaker attribution matches the cited passages. An exact reporting-period label can come from document metadata; its digits cannot support an unrelated financial value.
- Citation membership and whole-number-token checks do not establish semantic entailment or financial comparability. Generated research still requires source-level manual evaluation before any accuracy claim.
- Source text is delimited and escaped as data; the prompt forbids following embedded instructions.
