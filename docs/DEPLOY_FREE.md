# Deploying FINN for free, phone-ready, no sleep

FINN ships in two tiers. The **static snapshot** is the reliable submission link; the
**live backend** is optional and adds on-demand research.

| | Static snapshot (recommended link) | Live backend (optional) |
|---|---|---|
| Cost | Free | Free tier possible |
| Sleeps? | **Never** (it's just files on a CDN) | Free hosts sleep after ~15 min |
| Needs a key? | No | No for source extracts; optional Gemini/Groq/free-only OpenRouter key for synthesis |
| What works | Historical digest, saved briefs, quarterly, management, narrative, evidence, browser notebook | Also explicit current filings and current-source research where primary data is accessible |
| What's disabled | On-demand research, threshold re-tuning, custom dates | — |

Both are built from the same verified corpus and the same code. Nothing here needs a paid
model API, and the evaluator needs no key of their own.

---

## 1. Build the static snapshot (2 commands)

From the repo root, selecting keyless mode so the snapshot makes no model calls:

```bash
cd backend && env FINN_MODEL_PROVIDER=keyless \
  ../.venv/bin/python -m finn export-static
```

```bash
cd ../frontend && VITE_STATIC=1 npm run build
```

`frontend/dist/` is now a self-contained static site (~2.5 MB). It contains the app plus
`dist/snapshot/*.json` — the exported read models. No server, no database, no backend.

## 2. Publish it on a free CDN (never sleeps)

Pick one. All are free and serve over HTTPS.

- **Cloudflare Pages** — drag `frontend/dist/` onto the dashboard ("Upload assets"), or
  `npx wrangler pages deploy frontend/dist`. Per-asset limit 25 MiB (our largest file is tiny).
- **Netlify** — drag `frontend/dist/` onto app.netlify.com/drop, or `netlify deploy --dir=frontend/dist --prod`.
- **GitHub Pages** — commit `frontend/dist/` (or publish it from an action) and enable Pages.
  If served from a sub-path, build with `vite build --base=/<repo>/` so asset URLs resolve.

You get an HTTPS URL like `https://finn-demo.pages.dev`. Open it on any phone — no install,
no login.

## 3. Make the QR code + share card

```bash
python scripts/make_qr.py https://YOUR-URL --out docs/share
```

Writes `finn_qr.png`, `finn_qr.svg` and `finn_share_card.html` (open and print to PDF for a
one-page handout). The app itself also has a **Share** button (native share sheet on mobile,
copy-link elsewhere) that shares the exact company/brief you're viewing — deep links work.

---

## 4. (Optional) Live backend for on-demand research

The static site covers almost everything. Add the backend only if you want fresh research
for arbitrary tickers.

**Run it locally (free, no sleep while your machine is on):**

```bash
cd frontend && npm run build          # live build (no VITE_STATIC)
cd ../backend && ../.venv/bin/python -m finn serve --host 0.0.0.0 --port 8000
```

Open `http://<your-lan-ip>:8000` on a phone on the same Wi-Fi. For keyless operation select
`FINN_MODEL_PROVIDER=keyless`. For optional synthesis, configure the server as described in
`FREE_RESOURCES.md`. A Gemini example:

```bash
FINN_MODEL_PROVIDER=gemini GEMINI_API_KEY=your-free-key ../.venv/bin/python -m finn serve --port 8000
```

**Deploy it (free tier, but sleeps):** the `Dockerfile` + `render.yaml` blueprint deploy one
web service. The blueprint defaults to `FINN_MODEL_PROVIDER=keyless` and requires no key;
select a provider and add its server-side key to enable optional synthesis. Existing live
settings change only when explicitly updated. Free Render instances **sleep
after ~15 min** and cold-start in ~50 s — fine to try, but that's why the static snapshot is
the primary link. A paid instance with a persistent disk avoids sleep (see `docs/DEPLOYMENT.md`).

### Honest limits
- Free model tiers are **rate-limited**, not metered. On a 429 FINN falls back to the keyless
  verbatim source brief — it never breaks or spins forever.
- Historical replay is retained. The live app can explicitly check recent exchange notices and
  discover current research sources; a new request does not establish complete or continuous
  coverage. Last-checked, publication and reporting dates have separate meanings.
- On a datacenter IP, NSE may block fresh fetches; cached/replay access and clear
  source-failure states remain. Verify hosted fetch access before relying on it.

## Updating the already-submitted links

The post-submission changes are prepared locally. Deploy the backend first and check
`/api/health` for `capabilities.current_source_research=true`, then verify a current-filing
check and source brief. Publish the static bundle second, with the existing GitHub Pages base:

```bash
cd frontend
VITE_STATIC=1 \
VITE_LIVE_APP_URL=https://finn-mow9.onrender.com \
VITE_LIVE_PRICES_URL=https://raw.githubusercontent.com/arathii23/finn-enam/live-data/live_prices.json \
npm run build -- --base=/finn-enam/
```

Static research actions open a prefilled company/question in the live app; opening the link
does not submit it. The static site and live app have separate browser notebooks. Current jobs
and source-check caches on Render's ephemeral disk can disappear on restart; exported notebook
notes retain their original primary-source URLs and evidence locators.

## Published state and how it was published (4 November 2026)

- **Static demo:** https://arathii23.github.io/finn-enam/ is served from the `gh-pages` branch. The
  existing mechanism is a manual publication: export the snapshot from the production seed in
  keyless mode, build to a separate directory with the `/finn-enam/` base, then add it as a normal
  commit on top of `origin/gh-pages` (no force push). Rollback means checking out the previous
  `gh-pages` commit (`d1b5bc1` before the 4 November update).

  ```bash
  env FINN_MODEL_PROVIDER=keyless OPENAI_API_KEY='' ANTHROPIC_API_KEY='' GEMINI_API_KEY='' \
    GROQ_API_KEY='' OPENROUTER_API_KEY='' PYTHONPATH=backend .venv/bin/python -m finn export-static
  cd frontend && VITE_STATIC=1 VITE_LIVE_APP_URL=https://finn-mow9.onrender.com \
    VITE_LIVE_PRICES_URL=https://raw.githubusercontent.com/arathii23/finn-enam/live-data/live_prices.json \
    npm run build -- --base=/finn-enam/ --outDir ../tmp/finn-pages-release
  ```

  The production seed is `data/finn.sqlite3`. Never publish a QA database, `.env`, notebook exports
  or private conversation files.
- **Price feed cadence is best-effort.** The workflow is scheduled every five minutes, but GitHub
  throttles scheduled runs on low-activity repositories. Observed runs on 3 to 4 November were hours
  apart (19:51Z, 00:18Z, 06:43Z), so "refreshes every five minutes" is not a measured behaviour.
  The page always shows the feed's own "checked / last updated" time and each row's real trading
  date, which is the honest signal. A manual run is available with `gh workflow run live-prices.yml`.
  A recent check does not mean a new market session, and a missing previous session leaves the daily
  change blank rather than computing a multi-day move.
