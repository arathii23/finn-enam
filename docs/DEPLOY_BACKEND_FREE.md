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
  The seed rollback is the earlier Release `corpus-2026-11-03` (28 documents, 124 MB): point the
  `SEED_URL` line in the `Dockerfile` back at it. Keep both Releases.

## Prerequisites (free)
1. The corpus **GitHub Release** `corpus-2026-11-04` (asset `finn-seed.tar.gz`) must stay available;
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
- **First current read of a company (before the larger seed):** this was the slow step. Downloading and
  parsing a company's large annual report and transcripts on the free CPU exceeded the 180-second
  research limit for both Sun Pharma (a 345-page annual report) and Infosys. The job then ended with a
  plain-language message and a Retry action, and the retries finished in about 25 seconds. No
  out-of-memory restart occurred; the service stayed healthy. This still applies to any company whose
  documents are not in the seed.
- **Ephemeral store:** documents discovered at run time live in the instance's disk and are lost on
  redeploy, restart **and spin-down** (Render's free-tier documentation says all local files, including
  SQLite, are lost in those cases). I measured only the redeploy case (the corpus returned from 34 to
  the 28-document seed), but the 15-minute idle spin-down applies the same rule, so an idle instance
  forgets what it discovered. The seeded saved briefs persist because they are baked into the image.
  The browser notebook keeps its own data in the user's browser.
- **Sleep:** free instances sleep after about 15 minutes idle and take roughly a minute to wake.
  The static demo is the always-instant link.

## Honest limits
- No durable server-side history on the free setup. Do not promise it.
- The first research request for a company that is not in the seed can need one retry.
- NSE access from a datacenter can change; failures surface as named source gaps, not as all-clear.
- Budget guards remain ($5 total, $0.25 per job). They are ceilings, not permission to spend.

## Larger seed corpus (built and published on 4 November 2026; hosted results below)

Because the free instance forgets what it discovers, the practical fix is to ship more verified
documents inside the image's seed. `scripts/build_seed.py` builds one from an isolated copy of the
production store, using the same discovery code the live service runs (refresh mode, cutoff = now,
keyless, no model). Stages: `prepare`, `discover`, `verify`, `pack`. The production database was
never written (its SHA-256 was identical before and after).

**What the 4 November build produced** (`data/seed_build_2026_11_04/`, git-ignored):
- 56 new documents, all with verified publication proof; 84 documents and 27,570 passages in total.
- Current FY2025-26 annual report for 14 of 15 holdings (UltraTech's is excluded, see below); latest
  call transcripts with a verified management roster for 6 holdings (Infosys to 28 Oct 2026,
  HCLTech 15 Oct, HDFC Bank 23 Oct, Sun Pharma 6 Aug, UltraTech 27 Oct, CERA 12 Aug).
- Integrity checks passed: all 28 original documents unchanged, saved briefs identical, 108 replay
  read models compared with only the 15 "excluded documents" lists growing (newer files are
  correctly labelled as published after the replay cutoff), and 43 of 43 keyless quotes exact.
- A fresh extract booted keyless from the tarball (176 of 176 files matched their manifest hashes;
  `integrity_check` ok). The two current questions that exceeded 180 seconds on Render finished on
  the first attempt in 10 and 15 seconds on a Mac. Render's CPU is much slower; its earlier retry
  with stored documents took about 25 seconds, which is the realistic expectation.

**Gaps that stay gaps (the identity gates were not loosened):**
- Reliance (Media & Analyst Meet format), Bharti (the heading "Final Transcript" is read as a speaker
  and dialogue is unverified) and UltraTech (annual-report cover text unreadable) are excluded for
  "document identity check failed".
- ICICI Bank, HUL and Titan transcripts (and two of HDFC Bank's four) are eligible but have no verified
  management roster, so the product shows them without presenting speakers as management.
- Astral, L&T, Maruti and Trent transcript candidates were one-page exchange cover letters (16 such
  files, 9 typed as transcripts and 7 as annual reports, all correctly excluded); no current transcript was found for those four.

**Costs to weigh before publishing:** the tarball is **423 MB** (the current release is 124 MB) and
unpacks to about **550 MB** on the instance's disk (about 160 MB now). Render's free-tier disk and
build limits are not documented precisely, so measure the first build. The seed is dated (shown in
`SEED_MANIFEST.json`); filings after that date still need the on-demand check.

**Hosted results after publishing** (Release `corpus-2026-11-04`, source `93e0874`): Render built and
swapped in the new image in about 85 seconds with the 423 MB seed (the earlier instance kept serving
until it was ready). `/api/health` reports `seed.built_at 2026-11-04T08:42Z`, 84 documents and 27,570
passages. On the public free instance, with no retry: the Infosys current guidance question finished in
**12 s** and the Sun Pharma results-filing question in **36 s** (both previously failed at 180 s), each
with 5 of 5 highlights exact substrings of their cited passages and no model usage. After more than 15
idle minutes the instance woke in 32 s, had restarted (the two test jobs were gone; the saved list was
back to the three genuine briefs), still held the 84-document seed, and answered the same Infosys
question in **17 s** on the first attempt. Documents for companies outside the seed (or filings published
after the seed date) are still discovered on demand and forgotten again on spin-down.
