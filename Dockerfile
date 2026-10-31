# Single-service deployment: Vite build -> FastAPI serves API + static app on one origin.
# Prepared for Milestone 1; NOT built or deployed during this milestone.
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FINN_DATA_DIR=/data FINN_FRONTEND_DIST=/app/frontend/dist
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY manifests/ manifests/
COPY --from=web /web/dist frontend/dist
WORKDIR /app/backend
EXPOSE 8000
# One worker: SQLite + a single bounded research consumer by design.
CMD ["sh", "-c", "uvicorn finn.api:get_app --factory --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
