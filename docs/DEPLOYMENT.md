# Deployment plan (for approval — NOT yet executed)

> 3 November 2026: the user now requires deployment **without a model API key**. Read the current
> [Claude Code handoff](HANDOFF_CLAUDE_CODE.md) before using this historical proposal. Its API-funding
> steps are superseded, the blueprint still needs a keyless update, and the prices below require a
> fresh quote. A paid service plus persistent storage remains the proposed live architecture;
> hosting, static fallback, real-phone access and hosted persistence are unverified and unapproved.

No hosting has been provisioned, nothing is published, no card is on file. This document is the
concrete plan and cost so you can approve before anything is created. Prices checked on
render.com/pricing and Render docs, 31 October 2026 — confirm at purchase time.

Local readiness update, 31 October: 86 backend tests and the official frontend build pass;
seven real-app views were checked at 360/390/430 CSS px. This does not verify the container,
hosted source access, persistent disk or a physical phone. `render.yaml` is still only a proposal;
its model/caps now match local settings (Sonnet low effort, escalation off, $5/$0.25).

## Architecture fit

FINN is one process: FastAPI serves the API and the built React app on one origin; SQLite +
content-addressed PDFs live on a persistent disk; one bounded in-process job consumer. This maps to
**a single Render Web Service with a persistent disk** — no separate database, worker, Redis, or
object store needed. `Dockerfile` and `render.yaml` are already in the repo.

## Recommended plan and cost (single service)

| Item | Choice | Cost (USD/month) |
|---|---|---|
| Workspace | Hobby | $0 (flat Pro $25 only if you want unlimited seats — not needed) |
| Web service | **Starter** — 0.5 vCPU, 512 MB, always-on, can attach a disk | **$7.00** |
| Persistent disk | 2 GB SSD at $0.25/GB (local data dir measured 409 MB after all 15 holdings) | **$0.50** |
| Bandwidth | demo traffic is well within the included allowance; overage $0.15/GB | ~$0 |
| **Baseline total** | | **≈ $7.50 / month** |

This is within the prebuild spec's $15 first-month hosting ceiling.

**Memory caveat (must check first).** The largest annual report (HDFCBANK, 610 pages, ~18 MB) is
parsed with pypdf during cold ingestion. The 600-page extraction bound already produces partial
coverage, but 512 MB may still be tight while parsing. Two safe options:
1. Do all heavy ingestion locally (as now), commit the populated `data/` to the disk once, and run
   the Starter service in a serve-mostly mode → **$7.50/month** holds.
2. If you want cold ingestion to run on the host, use **Standard** (2 GB, $25) at least for the
   first ingestion, then scale back to Starter → first month ~**$25.50**, exceeding the $15 ceiling.

Recommendation: option 1 (ingest locally, deploy a populated disk) — cheapest and matches the
"saved demonstrations remain readable" requirement.

## Hard constraints (already handled in code / config)

- **Never the free tier for the live path:** free web services cannot attach a disk and sleep after
  15 min (30–50 s cold start), which would lose SQLite/job state. The disk + always-on Starter fixes
  both.
- **One instance only.** SQLite WAL + a single job consumer assume one instance; do not scale out.
- **Secret handling.** `ANTHROPIC_API_KEY` is set as a Render environment variable with `sync:false`
  (entered in the dashboard, never committed). `.env` is git-ignored. `render.yaml` already marks the
  key `sync:false`.
- **Spend caps.** `FINN_API_BUDGET_USD=5`, `FINN_JOB_BUDGET_USD=0.25` carried as env vars; the
  in-app ledger fails closed at the cap. Set Anthropic Console billing alerts as a second guard.

## Exact steps (when you approve)

1. Confirm the Anthropic account has a funded balance valid through the evaluation window (the
   current credits reportedly expire soon — saved demos stay readable without a call, but any new
   ticker needs a live, funded key).
2. Locally: ingest the full portfolio, run the suite, then `npm run build`.
3. Push the repo to GitHub (steps in `SUBMISSION_CHECKLIST.md`).
4. On Render: New → Blueprint → point at the repo (`render.yaml` is detected). Confirm Starter + a
   2 GB disk at `/data`.
5. Seed the disk with the populated `data/` (one-time upload, or let option 2 ingest once).
6. Set `ANTHROPIC_API_KEY` in the dashboard. Deploy.
7. Smoke test on the hosted URL: `/api/health`, open the Review queue, open a saved research result,
   run one fresh ticker, restart the service and confirm data persists.
8. Real-phone pass at 360–430 px.

## Not included / out of scope

No autoscaling, no managed Postgres/Redis, no object store, no custom domain. These would add cost
and are unnecessary for the prototype.
