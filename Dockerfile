# Single-service backend: Vite build -> FastAPI serves the API + React app on one origin.
# Self-contained and disk-free: the verified corpus (gitignored locally) is downloaded from the
# repo's public GitHub Release at build time, so this runs on a free host with no persistent disk
# (e.g. Render free). Defaults to the free Gemini provider; runs keyless if GEMINI_API_KEY is unset.
ARG SEED_URL=https://github.com/arathii23/finn-enam/releases/download/corpus-2026-11-03/finn-seed.tar.gz

FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ARG SEED_URL
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FINN_DATA_DIR=/app/data FINN_FRONTEND_DIST=/app/frontend/dist \
    FINN_MODEL_PROVIDER=gemini
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY manifests/ manifests/
COPY --from=web /web/dist frontend/dist
# Verified primary-source corpus (public NSE data), baked into the image.
RUN mkdir -p /app/data && curl -fsSL "$SEED_URL" -o /tmp/seed.tar.gz \
    && tar -xzf /tmp/seed.tar.gz -C /app/data && rm /tmp/seed.tar.gz \
    && test -f /app/data/finn.sqlite3 && chmod -R 777 /app/data
WORKDIR /app/backend
EXPOSE 8000
# One worker: SQLite + a single bounded research consumer by design. Binds the host's $PORT.
CMD ["sh", "-c", "uvicorn finn.api:get_app --factory --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
