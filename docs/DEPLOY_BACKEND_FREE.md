# Deploying the FINN live backend for free (Render)

The static demo (GitHub Pages) is complete and always-on. This adds the **live, on-demand
research** tier — fresh analysis for any NSE ticker, powered by Google Gemini's **free** key —
hosted free on **Render** (no credit card).

> Note: Hugging Face now charges for Docker/compute Spaces, so it is no longer a free option.
> Render still offers a free web-service tier. It **sleeps after ~15 min idle** and wakes on the
> next request (~1 min), and has **512 MB RAM** — fine for the seeded portfolio companies; a
> brand-new ticker with a very large annual report may exceed memory (it degrades to a clear
> source gap). The always-instant link remains the static demo.

Everything is pre-wired: the root `Dockerfile` builds the app and bakes in the corpus from this
repo's GitHub Release; `render.yaml` sets the free plan and the Gemini provider.

## Prerequisites (free)
1. The corpus **GitHub Release** exists (`finn-seed.tar.gz` on tag `corpus-2026-11-03`) — already published.
2. A free **Render** account: https://render.com (sign up with GitHub — no card).
3. A free **Gemini** API key: https://aistudio.google.com/apikey (no card).

## Deploy (about 5 minutes)
1. Render dashboard → **New +** → **Blueprint** → connect the GitHub repo `arathii23/finn-enam`.
   Render reads `render.yaml` and creates the `finn` web service on the **free** plan.
   (Or: **New +** → **Web Service** → pick the repo → Runtime **Docker** → Instance type **Free**.)
2. When prompted for env vars, set **`GEMINI_API_KEY`** = your free key. (Leave blank to run keyless.)
3. Click **Create / Deploy**. The first build takes a few minutes (builds the UI, installs deps,
   downloads the ~118 MB corpus into the image).
4. When it goes live you get an HTTPS URL like `https://finn-xxxx.onrender.com`.

## Verify
- Open `https://finn-xxxx.onrender.com/api/health` → JSON with `"model_provider":"gemini"` and a
  non-zero `corpus` document count.
- Open the app → **Research** → open a company → ask a question. With the key set you get a
  Gemini-written, source-validated brief; without it, the verbatim extractive brief.
- The Push digest, saved briefs, evidence and live prices all work, now served live.

## Honest limits
- Free instance **sleeps after ~15 min** idle; first hit after that is slow (~1 min cold start).
- **512 MB RAM**: seeded companies research fine (FTS over the stored corpus); discovering and
  parsing a brand-new very large PDF can exceed memory and will surface as a source gap, not a crash.
- New research jobs write to the in-image SQLite and are **ephemeral** (reset on restart/redeploy);
  the seeded saved briefs and corpus persist (baked into the image).
- Budget guards apply ($5 total / $0.25 per job of list-price reservations; the Gemini free tier
  reserves $0). A rate-limited model degrades to the keyless source brief.

If you'd rather not deal with sleep/memory: **Google Cloud Run** has a better free tier (more RAM,
fast cold starts) but requires a card on file. The same `Dockerfile` deploys there too.
