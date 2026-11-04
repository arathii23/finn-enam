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
    settings = service.settings if service is not None else get_settings()
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
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"state": "invalid_request", "message": str(exc)})

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

    @api.get("/api/companies/{symbol}/narrative")
    def narrative(symbol: str, mode: str = Query("replay", pattern="^(replay|live)$")):
        return wrap(svc.narrative_numbers, symbol, mode)

    @api.get("/api/companies/{symbol}/quarterly")
    def quarterly(symbol: str, mode: str = Query("replay", pattern="^(replay|live)$")):
        return wrap(svc.quarterly_results, symbol, mode)

    @api.post("/api/companies/{symbol}/quarterly/extract")
    def extract_quarterly(symbol: str, mode: str = Query("replay", pattern="^(replay|live)$")):
        return wrap(svc.quarterly_results, symbol, mode, allow_extract=True)

    @api.get("/api/companies/{symbol}/management")
    def management(symbol: str, mode: str = Query("replay", pattern="^(replay|live)$")):
        return wrap(svc.management_changes, symbol, mode)

    @api.post("/api/research", status_code=202)
    def research(req: ResearchRequest):
        return wrap(svc.submit_research, req)

    @api.get("/api/jobs/{job_id}")
    def job(job_id: str):
        return wrap(svc.job, job_id)

    @api.get("/api/research/saved")
    def saved_research(symbol: Optional[str] = None):
        return svc.saved_research(symbol)

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
                  volume_multiple: Optional[float] = Query(None, ge=0, le=100),
                  window: str = Query("24h", pattern="^(24h|7d|all|custom)$"),
                  filing_from: Optional[str] = None, filing_to: Optional[str] = None):
        return wrap(svc.portfolio_queue, mode, price_move_pct, volume_multiple, window, filing_from, filing_to)

    @api.get("/api/coverage")
    def coverage():
        return svc.coverage()

    @api.post("/api/portfolio/refresh")
    def refresh_portfolio(days: int = Query(7, ge=1, le=30)):
        return wrap(svc.refresh_current_portfolio, days)

    @api.get("/api/live-prices")
    def live_prices(price_move_pct: Optional[float] = Query(None, ge=0, le=100),
                    volume_multiple: Optional[float] = Query(None, ge=0, le=100)):
        # Optional free Yahoo EOD snapshot; separate from the verified replay corpus.
        return wrap(svc.live_prices, price_move_pct, volume_multiple)

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
