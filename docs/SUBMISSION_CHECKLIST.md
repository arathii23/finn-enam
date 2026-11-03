# Submission checklist — FINN (deadline 1 Nov 2026)

> Current-state update, 3 November 2026: an extension is confirmed. The latest suite is **119 passed**
> and the frontend build passes. The API balance is insufficient; a useful keyless fresh-research
> workflow is now required rather than funding the old API path. Use the acceptance gates in
> [HANDOFF_CLAUDE_CODE.md](HANDOFF_CLAUDE_CODE.md). The dated checklist below is historical and does
> not establish current public/phone readiness. No commit, deployment or submission has occurred.

Updated 31 October 2026. Nothing committed, pushed, publicly deployed or submitted in the M3/M4
continuation. Each outward step remains subject to the user's explicit go-ahead.

## Locally verified

- [x] Review/Push queue across all 15 holdings, with real NSE filings and 9 EOD sessions each.
- [x] Primary-source research, publication cutoff, identity checks, exact-passage evidence and gaps.
- [x] Deterministic Numbers vs Narrative, demonstrated on INFY; honest abstention elsewhere.
- [x] Saved quarterly tables: INFY, HCLTECH, ULTRACEMCO (3 metrics), HINDUNILVR (2); gaps elsewhere.
- [x] HDFCBANK/CERA appointment profiles quoted from primary filings; pre-window dates labelled.
- [x] Classification false positives repaired; configurable EOD thresholds and reviewed Undo exercised.
- [x] 86 backend tests; official TypeScript/Vite build; 21 mobile browser layout checks.
- [x] Local API budget $5 total / $0.25 per job; cumulative ledger $0.7947052 (104 calls).
- [x] Prepared deployment proposal matches those caps and the selected Sonnet research model.

## Before requesting shipping approval

- [ ] Review `BUILD_STATUS.md`, including quarterly/source gaps and browser-versus-phone limits.
- [ ] Review the existing small-sample evaluation in `docs/MODEL_EVALUATION.md`; do not imply a
      complete independent accuracy audit or unfamiliar-ticker/host certification.
- [ ] Confirm a funded server-side API credential through evaluation; exact credit expiry is unknown.
- [ ] Confirm the persistent-host plan and current pricing in `docs/DEPLOYMENT.md`.
- [ ] Preserve and prepare the ignored `data/` directory (SQLite, source PDFs, saved outputs and
      ledger) for an intentional private transfer to the eventual persistent disk. A repo alone
      does not contain the current demonstrations. Do not publish `.env`.
- [ ] Review all existing working-tree changes before any commit; nothing was committed by this pass.

## Shipping gates — explicit approval before each outward action

- [ ] Create/configure hosting and any paid resource only after concrete cost/configuration approval.
- [ ] Deploy, seed storage and verify health, saved research, evidence PDFs and a fresh ticker.
- [ ] Restart the hosted service and verify the data/results persist.
- [ ] Test the hosted URL on a physical phone; viewport emulation does not satisfy this gate.
- [ ] Approve repository creation/visibility, the final diff and commit, then approve the GitHub push.
      Preserve the prior authentic authorship/history; never commit credentials or the ignored corpus.
- [ ] Reconcile `docs/COVERING_EMAIL_DRAFT.md` with current features/limits and add verified hosted,
      repository and authentic-conversation links. It is still a draft, not an approved submission.
- [ ] Export/share the actual Claude and Codex conversations and verify evaluator access. The build
      history index is supplementary, not a replacement for authentic conversations.
- [ ] Approve and send the submission to assessment@enam.com with subject
      `ENAM - IIT screening - 2027`. No email has been sent.

## Limits to state candidly

Historical replay, selected stored appointment context, incomplete quarterly extraction coverage,
no intraday feed or notification delivery, and no universal model-accuracy claim. General source
discovery exists; cold unfamiliar-ticker and intended-host checks still need explicit verification.
