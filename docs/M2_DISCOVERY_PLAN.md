# FINN — next implementation plan

31 October 2026 (IST). Scope: generic primary-document discovery and source-quality validation. The portfolio queue and deployment remain later steps.

## Problem to remove

The current app resolves arbitrary NSE symbols but only knows annual-report/transcript URLs prefilled for INFY. A new company can therefore produce an honest empty screen, but cannot complete research. The next gate is a reusable discovery path, not more prepared answers.

## Decisions before implementation

1. Use the NSE annual-report index and dated corporate announcement records as the discovery layer. Download only their actual attached files, validate identity/type, and preserve exact publication evidence. Do not use search snippets, company facts from model memory or ticker-specific URL mappings.
2. Preserve the historical replay cutoff. Discover the latest eligible annual report and up to two eligible transcripts using bounded lookback windows. The report's fiscal period and publication time are different fields. Future documents cannot become eligible merely because they are in a current index.
3. Infer period metadata conservatively from a document's own title/header. Unknown period remains unknown, rather than guessed from its filename or announcement date. Verify company and document type before admitting passages.
4. Run discovery inside the existing research job when a required source type is absent. Keep visible stages, bounded network calls/downloads and truthful partial results. A source failure must not trigger model-memory completion.
5. Keep source provenance and files persistent. Reuse valid extracted bytes, and avoid changing already verified publication proof into weaker evidence when a file is revisited.
6. Keep the existing $5 global API ceiling and $0.25 job ceiling. Public-source discovery itself does not call a model. The small model evaluation gets at most $1 additional usage and shares the global ledger.

## Parallel responsibilities

- Main implementation: discovery module, publication/period safeguards, job/API/UI integration and meaningful regression tests.
- Independent source audit: examine two non-demo companies in different sectors, including a smaller issuer; record actual endpoint fields and parsing problems without changing application code.
- Independent model check: ten labelled evidence packets, response snapshots, critical-field audit and honest pass/fail limits. No app modifications by that worker.

## Acceptance checks

- Two non-demo companies complete discovery from empty company/document caches without prefilled document URLs. At least one annual report and one transcript each have correct identity, publication proof, extraction and usable source passages.
- Wrong-company records, future publications, transcript invitations/recordings and malformed files cannot masquerade as valid research documents.
- A source index without a publication date requires a dated exchange attachment record. Missing proof stays excluded from replay.
- A period absent from source text is not manufactured. Ambiguous or unsupported facts remain missing.
- A research request through the app actually discovers sources and returns citations or explicit bounded gaps; UI contains no command-line instruction as the user's normal recovery path.
- Existing INFY replay, budget recovery, saved results and evidence navigation continue working.
- Record source URLs/hashes, exact checks, model usage and cold-run timings. Local success is not proof of hosted access or physical-phone behaviour.

## Cuts and stopping rules

No automatic guidance verdicts, ticker-specific final answers, generic web-search service, native app, vector database, paid document provider or portfolio expansion in this pass. Start with a bounded NSE path; report its coverage limit if real source access fails. Do not claim universal coverage from two successful companies. A complete blocked run is reported with its evidence, not silently replaced by a prepared showcase.

## Sequence

Inspect current contracts and source behaviour → implement discovery/parser safeguards → synthetic failure regressions → real cold discovery → source-level audit → app/browser integration check → update BUILD_STATUS and authentic history.

The plan will be revised only where actual source observations require it; those changes and their evidence will be recorded below.
