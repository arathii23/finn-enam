# FINN build status — Milestone 1

Updated 30 Oct 2026 (IST). **Milestone 1 status: PARTIALLY PASSED. The code path is built and its logic is tested; it has not yet run on real NSE data.**

## Implemented

- **Contracts and storage.** Pydantic contracts (company, fetch attempt, announcement, document version, passage, EOD observation, research output, job). SQLite stores metadata, jobs and the model-cost ledger, with FTS5 for passages. Source files are immutable and keyed by sha256.
- **Guarded retrieval.** The fetcher is HTTPS-only and rejects private hosts. It re-validates every redirect hop and caps downloads at 50 MB. Bytes are checked against the expected type, so an HTML page served as "PDF" is rejected. Every attempt is recorded with a state from the spec vocabulary.
- **NSE adapters, reusable for any symbol.**
  - Identity from `EQUITY_L.csv`. Unknown symbols and a missing source are reported as separate states.
  - `sec_bhavdata_full` daily files. A missing file is recorded as `not_found`; FINN does not assume a holiday.
  - The corporate-announcements API, with a cookie warm-up and a check that each record belongs to the requested company.
  - The annual-report index.
- **Documents.**
  - The exchange record whose attachment URL equals the document URL supplies the publication time.
  - A generic identity check runs on the first pages: legal name, type terms and fiscal-period spellings.
  - Text is extracted page by page with pypdf. Transcripts are split by speaker, and passages keep the one-based PDF page index.
  - Substantive announcement attachments are fetched by a generic category rule and linked to the announcement.
- **Replay.** The manifest holds metadata only: filings 17–30 Apr 2025, evidence cutoff 30 Apr 2025 23:59 IST. The cutoff filter runs before retrieval. The FY25 annual report is ingested as a negative fixture.
- **Research job.** Stages: resolve → find eligible documents → read → prepare. Retrieval is bounded, with separate sections for annual-report context, transcript commentary and the event filing.
  - The OpenAI Responses adapter (spec §6 models, configurable) uses a strict JSON schema, list-price reservations, per-job and total caps, and one escalation.
  - Validation drops statements with unknown ids, the wrong document type or unsupported numbers.
  - Deterministic coverage gaps are reported.
  - Idempotent reuse avoids duplicate runs, and jobs left unfinished by a restart are marked `interrupted`.
- **API and UI.** FastAPI serves the routes and the built frontend on one origin. The React mobile UI covers:
  - A replay banner that is always visible.
  - Ticker entry.
  - Company identity, announcements with "Research this event", an EOD table, eligible and excluded documents, and source coverage.
  - Research progress with elapsed time, and the research view.
  - An evidence sheet with metadata, the passage, "Open PDF at page N" (cached copy) and "Open original".
  - Loading, partial, empty, unknown-ticker and failure states.
- **Verification tooling.**
  - `python -m finn verify` runs 7 checks on real data.
  - `scripts/smoke.py` checks startup, HTTP routes and restart persistence.
  - `scripts/m1_verify.sh` runs everything end to end and logs to `data/verification/`.
- **Deployment design.** `Dockerfile` (Vite build stage plus Python runtime, one worker) and `render.yaml` (one instance with a disk). **Neither was built, applied or deployed.**

## Tested, with results

The build ran in a cloud workspace whose network policy blocks nseindia.com, api.openai.com, PyPI and npm. The shell on the user's Mac had no network at all. Everything below ran on **synthetic fixtures** for a fictional "Testco Industries Limited", served through a mocked network.

| Check | Result | What it actually covered |
|---|---|---|
| `pytest backend/tests` (14 tests) | **14/14 pass** | Identity resolution and the unknown-vs-unavailable states. URL and byte guards, including HTML served as a PDF. Provenance fields (hash, URL, retrieval time, period, second-precision exchange time, date-only end-of-day rule). Speaker and page locators. Cutoff exclusions (after-cutoff, unproven, and an earlier-cutoff probe excluding a transcript). Honest partial output without a key. Escaping of embedded markup. Validation of mocked model output (2 bad claims removed). The budget cap blocking a call before any network request. Job flow, idempotency and restart. Event research. The real-data checker run on synthetic data. |
| `tests/ui_check.py` (Playwright Chromium; 360/390/430 px) | **57/57 pass** | Replay banner and dates. Company, research and evidence screens. No horizontal overflow. Touch targets ≥44 px. Evidence page locator matches the citation. The cached-PDF route returns `%PDF-`. Escape closes the sheet and returns focus. Unknown-ticker, loading and server-failure states. No JS errors. The `/api` calls were answered by the real service layer, **not** by FastAPI. |
| esbuild bundle of the frontend | builds | The TypeScript typecheck (`tsc`) and the Vite build were **not run**: their packages are unavailable here. |
| `py_compile` of `api.py` and `smoke.py`; `bash -n m1_verify.sh` | ok | Syntax only. The FastAPI app was **not started**, because FastAPI is not installable here. |

**Not run:**
- Real NSE retrieval.
- The real-data checks (M1-01…07).
- FastAPI startup and HTTP smoke.
- The Vite/tsc build.
- Any model call.
- A real phone test.

## Known failures, blockers and missing credentials

- **No real sources retrieved yet.** This blocks requirements 1–5 from being demonstrated on genuine data. `bash scripts/m1_verify.sh` on a machine with normal internet runs all of it and writes the reports to `data/verification/`.
- **`OPENAI_API_KEY` is not set.** Research prose, the management-commentary summary and the follow-up question are not generated. The UI and checks report `model_unavailable`, and check M1-07 can only reach `partial`. The gpt-6-luna and gpt-6.1-sol models from the spec are unverified for this account.
- **Open risks for the real run:**
  - The INFY FY24 annual-report publication proof depends on finding the attachment in the June 2024 exchange feed or the NSE annual-report index. If neither lists it, the report is correctly **excluded** from replay, and business context will show as a gap.
  - The NSE website API may reject non-browser clients.
  - Extracting the 380-page board bundle may take a few minutes.
- Printed page numbers are not identified; the PDF page index is shown instead and labelled as such.
- Scope still outstanding after M1: the 15-holding queue, POLYCAB and the cold non-IT runs, the live mode, and the HCLTECH January transcript publication proof.

## Sources successfully retrieved

**None in this session.** Network policy blocked every source host. No real company data is in the repository. The candidate URLs are in `manifests/replay_2025_04.json`, taken from the supplied audit.

## Next concrete task

Run `bash scripts/m1_verify.sh` from the project folder on the Mac with internet access. Then review `data/verification/m1_checks.md` and `startup_smoke.json`, fix any real-source failures (headers, availability matching, identification terms), and update this file with the measured results. After that, set a runtime API key, run the small model evaluation from spec §6, and re-run M1-06 and M1-07 on generated claims.
