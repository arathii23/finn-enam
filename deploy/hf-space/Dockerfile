# FINN live backend for Hugging Face Spaces (Docker SDK). Free Gemini-powered research.
#
# This file + README.md are the ENTIRE Space repo. The image pulls the app from the public
# GitHub repo and the verified corpus from its GitHub Release, builds the React app, and serves
# the FastAPI API + UI on one origin. No secrets are baked in; set GEMINI_API_KEY as a Space
# secret for free AI synthesis (omit it to run keyless — the extractive source brief still works).

ARG REPO=https://github.com/arathii23/finn-enam
ARG SEED_URL=https://github.com/arathii23/finn-enam/releases/download/corpus-2026-11-03/finn-seed.tar.gz

# ---- build the React app (live mode: it calls /api on the same origin) ----
FROM node:22-slim AS web
ARG REPO
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 "$REPO" /src
WORKDIR /src/frontend
RUN npm install --no-audit --no-fund && npm run build

# ---- backend runtime ----
FROM python:3.12-slim
ARG REPO
ARG SEED_URL
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FINN_DATA_DIR=/app/data FINN_FRONTEND_DIST=/app/frontend/dist \
    FINN_MODEL_PROVIDER=gemini
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN git clone --depth 1 "$REPO" /tmp/src \
    && cp -r /tmp/src/backend backend && cp -r /tmp/src/manifests manifests && rm -rf /tmp/src
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY --from=web /src/frontend/dist frontend/dist
# Verified primary-source corpus (public NSE data), baked into the image at build time.
RUN mkdir -p /app/data && curl -fsSL "$SEED_URL" -o /tmp/seed.tar.gz \
    && tar -xzf /tmp/seed.tar.gz -C /app/data && rm /tmp/seed.tar.gz \
    && test -f /app/data/finn.sqlite3
# A writable home for the SQLite WAL and any new (ephemeral) research jobs.
RUN chmod -R 777 /app/data
EXPOSE 7860
WORKDIR /app/backend
# One worker by design (single SQLite + bounded research consumer).
CMD ["sh", "-c", "uvicorn finn.api:get_app --factory --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
