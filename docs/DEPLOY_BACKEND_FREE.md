# Deploying the FINN live backend for free (Hugging Face Spaces)

The static demo covers almost everything. This adds the **live, on-demand research** backend —
fresh analysis for any NSE ticker, powered by Google Gemini's **free** tier, with live Yahoo
prices. Hosted free on **Hugging Face Spaces** (Docker): 16 GB RAM (enough to parse large PDFs),
HTTPS, no card required. Free Spaces sleep after ~48 h of no visits and wake on the next visit.

The Space repo is tiny — just `deploy/hf-space/Dockerfile` + `deploy/hf-space/README.md`. The
image pulls the app from this public GitHub repo and the verified corpus from this repo's GitHub
Release, so you don't upload any large files to Hugging Face.

## Prerequisites (one-time, free)
1. A **GitHub Release** of the corpus exists on this repo (asset `finn-seed.tar.gz`). If not,
   create it from the repo root (publishes the public primary-source data):
   ```bash
   tar -czf finn-seed.tar.gz -C data finn.sqlite3 sources
   gh release create corpus-2026-11-03 --repo arathii23/finn-enam \
     --title "FINN corpus seed" --notes "Primary-source corpus for the backend." \
     finn-seed.tar.gz
   ```
2. A free **Hugging Face** account: https://huggingface.co/join
3. A free **Gemini** API key: https://aistudio.google.com/apikey

## Deploy (about 5 minutes)
1. Create a new Space: https://huggingface.co/new-space → **SDK: Docker**, blank template,
   name e.g. `finn`. This gives you a git repo at
   `https://huggingface.co/spaces/<you>/finn`.
2. Put the two files in it and push:
   ```bash
   git clone https://huggingface.co/spaces/<you>/finn && cd finn
   cp /path/to/finn-enam/deploy/hf-space/Dockerfile .
   cp /path/to/finn-enam/deploy/hf-space/README.md .
   git add Dockerfile README.md && git commit -m "FINN backend" && git push
   ```
   (First push asks for your HF username + an access token as the password:
   https://huggingface.co/settings/tokens — a "write" token.)
3. In the Space → **Settings → Variables and secrets → New secret**:
   `GEMINI_API_KEY` = your free key. (Skip to run keyless.)
4. The Space builds (a few minutes — it clones the repo, builds the UI, downloads the corpus).
   When it's running, your live backend is at `https://<you>-finn.hf.space`.

## Verify
- Open `https://<you>-finn.hf.space/api/health` → JSON with `"model_provider":"gemini"` and a
  non-zero `corpus` count.
- Open the app on a phone → **Research** tab → open a company → ask a question. With the key set,
  you get a Gemini-written, source-validated brief; without it, the verbatim extractive brief.
- Live prices and the full digest work the same as the static demo, now served live.

## Notes & limits (honest)
- Free Spaces **sleep after ~48 h** of inactivity and cold-start on the next visit (~30–60 s).
  The static GitHub Pages demo remains the always-instant link; this backend is the "live" tier.
- New research jobs write to the in-image SQLite and are **ephemeral** (lost on restart); the
  seeded saved briefs and corpus persist because they're baked into the image.
- On a datacenter IP, NSE may throttle fresh discovery for brand-new tickers; portfolio tickers
  already have their sources in the seed, and failures surface as explicit source gaps.
- Budget guards still apply ($5 total / $0.25 per job of list-price reservations; Gemini free
  tier reserves $0). A rate-limited model degrades to the keyless source brief.
