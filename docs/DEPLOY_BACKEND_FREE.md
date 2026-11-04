# Deploying the FINN live backend for free (Render)

The static demo (GitHub Pages) is always on. The live backend adds on-demand research for
any NSE ticker, an explicit current-filings check and the browser notebook's live links. It runs
on Render's **free** web-service tier (no card). The root `Dockerfile` builds the app and bakes in
the corpus from this repo's GitHub Release; `render.yaml` sets the free plan and keyless mode.

Current deployment: https://finn-mow9.onrender.com (service `finn`, one free instance, one worker).

## Default mode is keyless

`FINN_MODEL_PROVIDER=keyless` is the default in code, the `Dockerfile` and `render.yaml`. No model
key is needed, and the app makes no model calls. Optional providers (Gemini, Groq, free-only
OpenRouter) are explicit operator choices described in `docs/FREE_RESOURCES.md`.

Dashboard variables can override Docker defaults. On 4 November the service first reported
`gemini` (an older dashboard value) and about a minute later reported `keyless` after the blueprint
change synced; the dashboard itself was not inspected, so treat the blueprint sync as the likely
cause. Always confirm the effective mode instead of assuming it:

```bash
curl -s https://finn-mow9.onrender.com/api/health
```

Expect `"model_provider":"keyless"`, `"model_configured":false`, a non-zero `corpus` document count
and `capabilities.current_source_research` set to `true`. A provider secret stored in the dashboard
is left in place by this change; it is simply not used while the provider is `keyless`.

## Publishing

- **Backend:** the service auto-deploys on every push to `main` (verified: a push went live in
  about one to two minutes). A free instance restarts during the deploy, so the first request
  right after it can return a gateway error; retry after a few seconds.
- **Static demo:** built from the production seed in keyless mode and published to the existing
  `gh-pages` branch as a normal fast-forward commit (no force push). See `docs/DEPLOY_FREE.md`.
- **Rollback references (4 November 2026):** source `main` was `472813c` before the update;
  `gh-pages` was `d1b5bc1`. Check out those commits to restore the earlier source or static demo.

## Prerequisites (free)
1. The corpus **GitHub Release** `corpus-2026-11-03` (asset `finn-seed.tar.gz`) must stay available;
   the Docker build downloads it. It holds the genuine saved demonstrations. Never replace it with a
   QA or temporary database.
2. A free **Render** account connected to GitHub (no card).
3. Optional: a free provider key, added only as a Render environment variable (never in the repo
   or in any `VITE_*` variable).

## First deploy (about 5 minutes)
1. Render dashboard → **New +** → **Blueprint** → connect `arathii23/finn-enam`. Render reads
   `render.yaml` and creates the `finn` service on the **free** plan.
2. Click **Deploy**. The first build takes a few minutes (UI build, dependencies, ~118 MB corpus).
3. Open the service URL and check `/api/health` as above.

## Measured behaviour on the free instance (4 November 2026)

- **Replay data, saved research and evidence:** fast; the three genuine saved briefs and cached
  PDFs (a 3.7 MB PDF streamed with `application/pdf`) were served.
- **Explicit current-filings check:** the hosted app reached NSE from Render and validated 14 of 15
  holdings (53 announcements). SUNPHARMA stayed partial because one record failed validation; the
  page names it instead of showing 15/15. A repeat inside 15 minutes is served from the cache at its
  original timestamps.
- **First current read of a new company:** this is the slow step. Downloading and parsing a company's
  large annual report and transcripts on the free CPU exceeded the 180-second research limit for
  both Sun Pharma (a 345-page annual report) and Infosys. The job then ends with a plain-language
  message and a Retry action, because documents already read are stored. The retries finished in
  about 25 seconds. No out-of-memory restart occurred in these runs; the service stayed healthy.
- **Ephemeral store:** documents discovered at run time live in the instance's disk and are lost on
  restart or redeploy (the corpus returned from 34 to the 28-document seed after a deploy). The
  seeded saved briefs persist because they are baked into the image. The browser notebook keeps
  its own data in the user's browser.
- **Sleep:** free instances sleep after about 15 minutes idle and take roughly a minute to wake.
  The static demo is the always-instant link.

## Honest limits
- No durable server-side history on the free setup. Do not promise it.
- The first research request for a company that is not in the seed can need one retry.
- NSE access from a datacenter can change; failures surface as named source gaps, not as all-clear.
- Budget guards remain ($5 total, $0.25 per job). They are ceilings, not permission to spend.
