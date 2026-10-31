"""FastAPI HTTP layer. Routes accept internal IDs only (no arbitrary fetch URLs).
The built React app is served from the same origin."""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .contracts import ResearchRequest
from .service import App, NotFound


def create_app(service: Optional[App] = None) -> FastAPI:
    settings = get_settings()
    svc = service or App(settings)
    api = FastAPI(title="FINN", version="0.1.0-m1")
    api.state.svc = svc

    def wrap(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except NotFound as exc:
            status = 404 if exc.state in ("not_found", "unknown_symbol", "file_missing") else 409
            if exc.state == "source_unavailable":
                status = 503
            raise HTTPException(status_code=status, detail={"state": exc.state, "message": str(exc)})

    @api.get("/api/health")
    def health():
        return svc.health()

    @api.get("/api/replay")
    def replay():
        return svc.replay_info()

    @api.get("/api/companies/{symbol}")
    def company(symbol: str):
        return wrap(svc.company, symbol)

    @api.get("/api/companies/{symbol}/overview")
    def overview(symbol: str, mode: str = Query("replay", pattern="^(replay|live)$")):
        return wrap(svc.company_overview, symbol, mode)

    @api.post("/api/research", status_code=202)
    def research(req: ResearchRequest):
        return wrap(svc.submit_research, req)

    @api.get("/api/jobs/{job_id}")
    def job(job_id: str):
        return wrap(svc.job, job_id)

    @api.get("/api/evidence/{passage_id}")
    def evidence(passage_id: str):
        return wrap(svc.evidence, passage_id)

    @api.get("/api/documents/{version_id}")
    def document(version_id: str):
        return wrap(svc.document, version_id)

    @api.get("/api/documents/{version_id}/file")
    def document_file(version_id: str):
        path = wrap(svc.document_file, version_id)
        return FileResponse(path, media_type="application/pdf",
                            headers={"Content-Disposition": f'inline; filename="{version_id}.pdf"',
                                     "Cache-Control": "public, max-age=86400, immutable"})

    @api.get("/api/portfolio")
    def portfolio(mode: str = Query("replay", pattern="^(replay|live)$"),
                  price_move_pct: Optional[float] = Query(None, ge=0, le=100),
                  volume_multiple: Optional[float] = Query(None, ge=0, le=100)):
        return svc.portfolio_queue(mode, price_move_pct, volume_multiple)

    @api.get("/api/coverage")
    def coverage():
        return svc.coverage()

    dist = settings.frontend_dist
    if (dist / "index.html").exists():
        if (dist / "assets").exists():
            api.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @api.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "not found"}, status_code=404)
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and dist in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return api


app = None


def get_app() -> FastAPI:
    global app
    if app is None:
        app = create_app()
    return app
