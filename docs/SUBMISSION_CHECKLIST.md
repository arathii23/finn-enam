# Submission checklist — FINN (deadline 1 Nov 2026)

Deliverables required by the brief: mobile prototype (deployed link), GitHub repo, authentic AI
build history, covering email to assessment@enam.com, subject "ENAM - IIT screening - 2027".

## Done (verified in the build)

- [x] Two hero workflows: Review/Push queue + Pull research, mobile-first.
- [x] Three working data sources: NSE EOD, exchange announcements/filings, annual reports +
      transcripts — real data for INFY, CERA, HDFCBANK; identity resolves for all NSE tickers.
- [x] Primary-source discipline enforced in code; per-claim evidence to the exact PDF page.
- [x] Historical replay with a fixed publication cutoff; separate general-ticker path.
- [x] Prioritised digest with explainable tiers + configurable EOD anomaly flags.
- [x] Cost ledger + budget caps; Sonnet selected after a labelled model evaluation.
- [x] Source-audit repairs (v1.8) verified at source; 49 Python tests, 30 queue UI checks pass.
- [x] Covering-email draft (`docs/COVERING_EMAIL_DRAFT.md`), deployment plan (`docs/DEPLOYMENT.md`).

## You must do (needs your machine / accounts — I can't from here)

1. **Ingest the other 12 holdings** (your Mac has network; my sandbox does not):
   ```bash
   cd ~/Downloads/ENAM_Holdings && . .venv/bin/activate && cd backend
   python -m finn ingest HCLTECH RELIANCE ICICIBANK BHARTIARTL LT MARUTI \
       HINDUNILVR SUNPHARMA ULTRACEMCO TITAN TRENT ASTRAL
   ```
   (INFY, CERA, HDFCBANK are already ingested. This populates the Review queue fully.)
2. **Build the frontend for real** (my committed `frontend/dist` is an esbuild interim; your Mac has
   the macOS node_modules for the official Vite build):
   ```bash
   cd ~/Downloads/ENAM_Holdings/frontend && npm install && npm run build
   ```
3. **Run and phone-test:** `cd ../backend && python -m finn serve`, open on a phone at the LAN IP.
4. **GitHub repo:** the repo is already initialised and has a clean initial commit on `main`
   (`.env` and `data/` are git-ignored — no secrets or large binaries). Create an empty repo named
   `finn-enam` (or your choice) at github.com/arathii23 — public, or private with the evaluator
   invited — then from your Mac:
   ```bash
   cd ~/Downloads/ENAM_Holdings
   git remote add origin https://github.com/arathii23/finn-enam.git   # or the SSH URL
   git push -u origin main
   ```
   If you want the evaluator to see the ingested corpus (saved research/evidence), package `data/`
   separately — it is deliberately git-ignored to keep the repo clean and keyless.
5. **Deploy** (optional but expected): approve `docs/DEPLOYMENT.md` (~$7.50/mo), then follow its steps.
6. **Authentic AI build history:** export/share-link this Claude Code conversation (and the earlier
   planning/Codex ones), verify an evaluator can open them, and paste the links into the email.
   `docs/BUILD_HISTORY.md` is an index, not a substitute.
7. **Send the email:** fill the brackets in `docs/COVERING_EMAIL_DRAFT.md`, attach/link, send to
   assessment@enam.com with the exact subject.

## Honest limitations to state in the email

- Full portfolio population and the official Vite build happen on your machine (above).
- Deployment/phone tests pending your approval/run.
- Automated beat/miss comparisons and live (non-replay) research are deliberately out of scope.
