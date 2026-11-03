# Deploying FINN for free, phone-ready, no sleep

FINN ships in two tiers. The **static snapshot** is the reliable submission link; the
**live backend** is optional and adds on-demand research.

| | Static snapshot (recommended link) | Live backend (optional) |
|---|---|---|
| Cost | Free | Free tier possible |
| Sleeps? | **Never** (it's just files on a CDN) | Free hosts sleep after ~15 min |
| Needs a key? | No | No (keyless) — or a free Gemini key for AI synthesis |
| What works | Push digest, all saved briefs, quarterly, management, narrative, evidence | Everything + fresh on-demand research for any NSE ticker |
| What's disabled | On-demand research, threshold re-tuning, custom dates | — |

Both are built from the same verified corpus and the same code. Nothing here needs a paid
model API, and the evaluator needs no key of their own.

---

## 1. Build the static snapshot (2 commands)

From the repo root, with model keys unset so the snapshot is provably model-free:

```bash
cd backend && env OPENAI_API_KEY='' ANTHROPIC_API_KEY='' GEMINI_API_KEY='' \
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

Open `http://<your-lan-ip>:8000` on a phone on the same Wi-Fi. For keyless operation set no
keys. For **free AI synthesis**, get a free key at https://aistudio.google.com/apikey and:

```bash
FINN_MODEL_PROVIDER=gemini GEMINI_API_KEY=your-free-key ../.venv/bin/python -m finn serve --port 8000
```

**Deploy it (free tier, but sleeps):** the `Dockerfile` + `render.yaml` blueprint deploy one
web service. The blueprint defaults to `FINN_MODEL_PROVIDER=gemini` with a blank key (keyless);
paste a free Gemini key in the dashboard to enable synthesis. Free Render instances **sleep
after ~15 min** and cold-start in ~50 s — fine to try, but that's why the static snapshot is
the primary link. A paid instance with a persistent disk avoids sleep (see `docs/DEPLOYMENT.md`).

### Honest limits
- Free model tiers are **rate-limited**, not metered. On a 429 FINN falls back to the keyless
  verbatim source brief — it never breaks or spins forever.
- The live corpus is a stored April-2025 replay, not a real-time feed; every date is labelled.
- On a datacenter IP, NSE may block fresh fetches; cached/replay access and clear
  source-failure states remain. Verify hosted fetch access before relying on it.
