# Run and inspect FINN

FINN serves a FastAPI backend and a React/Vite frontend. The default research mode selects verbatim primary-source quotations without a model call. The public demo and the live research app are linked from the [repository README](../README.md).

## Local setup

From the repository root, with Python 3.10+ and Node.js installed:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r app/backend/requirements-dev.txt
npm --prefix app/frontend ci
npm --prefix app/frontend run build
```

Optional server settings go in a root-level `.env`, based on [the example](../.env.example). Keep the keyless default unless explicitly choosing a model provider. No provider key belongs in a browser variable.

To serve the built app:

```bash
PYTHONPATH=app/backend .venv/bin/python -m finn serve
```

Open `http://127.0.0.1:8000`. A fresh checkout has no private local corpus. Ingest public source data before expecting populated research:

```bash
PYTHONPATH=app/backend .venv/bin/python -m finn ingest INFY
PYTHONPATH=app/backend .venv/bin/python -m finn verify --symbol INFY
```

The networked setup and ingestion check is also available as `bash app/scripts/m1_verify.sh`. It downloads dependencies and public sources; inspect its scope before running it.

## Verify changes

```bash
PYTHONPATH=app/backend .venv/bin/python -m pytest -q app/backend/tests
npm --prefix app/frontend run build
cd app/frontend
VITE_STATIC=1 VITE_LIVE_APP_URL=https://finn-mow9.onrender.com npm run build -- --base=/finn-enam/ --outDir ../../tmp/static-check
```

For the production Pages build, retain the feed settings in [the publication guide](DEPLOY_FREE.md). The static snapshot is exported separately from the verified corpus; a frontend build alone does not generate or refresh it.

## Structure and data

- `app/backend/finn/`: guarded source retrieval, SQLite/FTS5, publication eligibility, research, results, digest, phone subscriptions and HTTP routes.
- `app/backend/tests/`: synthetic regression and service checks; live integration evidence is recorded separately in the dated reports.
- `app/frontend/`: mobile UI, exact-source evidence, notebook and personal alert setup.
- `app/manifests/`: portfolio and replay-source metadata. The historical cutoff is preserved.
- `app/scripts/`: seed preparation, QR generation, data publishing, source probes and alert workers.
- `docs/evaluation/`: dated verification reports served by the Trust view.

The default runtime data directory is root-level `data/` and the optional configuration file is root-level `.env`. These stay outside Git. Phone preferences use the configured private Redis store; notification transport uses the optional QStash relay and ntfy. The management access code and notification topic are separate credentials.

## Hosting

The root Dockerfile builds `app/frontend/`, installs `app/backend/` and bundles the public seed. The runtime layout mirrors the repository, with the backend at `/app/app/backend`. Render's existing root Dockerfile and HTTPS routes are unchanged. GitHub Pages publishes from the separate `gh-pages` branch.

See [phone setup](PHONE_ALERTS_PILOT.md), [Render deployment](DEPLOY_BACKEND_FREE.md) and [Pages publication](DEPLOY_FREE.md). Free-host schedules and source availability are best effort; rely on displayed timestamps and coverage.
