"""Anonymous phone subscription API. Bearer credentials never appear in links."""
from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from .phone_alerts import GROUPS, PhoneAlerts, PhoneError, RedisPhoneStore


class PhonePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbols: list[str] = Field(min_length=1, max_length=15)
    groups: list[str] = Field(min_length=1, max_length=4)
    active: bool = False


def phone_router(svc, manager: PhoneAlerts | None = None):
    settings = svc.settings
    if manager is None:
        store = None
        if settings.phone_redis_url and settings.phone_redis_token:
            try:
                store = RedisPhoneStore(settings.phone_redis_url, settings.phone_redis_token)
            except ValueError:
                logging.getLogger(__name__).warning("Phone alert storage requires a valid Upstash HTTPS REST URL.")
        companies = []
        for symbol in svc.portfolio.get("symbols", []):
            row = svc.store.query_one("SELECT legal_name FROM companies WHERE symbol=?", (symbol,))
            companies.append({"symbol": symbol, "name": row["legal_name"] if row else symbol})
        manager = PhoneAlerts(store, companies)
    router = APIRouter(prefix="/api/phone", tags=["phone alerts"])

    def token(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Your alert access code is missing.")
        return authorization[7:]

    def run(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except PhoneError as exc:
            raise HTTPException(exc.status, str(exc)) from None

    @router.get("/catalog")
    def catalog():
        configured = manager.store is not None
        return {"available": configured, "companies": manager.companies,
                "groups": [{"id": key, **{k: v for k, v in row.items() if k != "categories"}} for key, row in GROUPS.items()],
                "last_check": run(manager.store.status) if configured else None,
                "cadence": "Checks are scheduled twice an hour. Free hosting can delay them.",
                "max_daily": 3, "test_cadence": "Test deliveries are checked about every five minutes. GitHub can delay a check."}

    @router.get("/subscription")
    def subscription(authorization: str | None = Header(None)):
        return run(manager.get, token(authorization))

    @router.put("/subscription")
    def save(req: PhonePreferences, request: Request, authorization: str | None = Header(None)):
        return run(manager.save, token(authorization), req.symbols, req.groups, req.active,
                   request.client.host if request.client else "unknown")

    @router.delete("/subscription")
    def delete(authorization: str | None = Header(None)):
        return run(manager.delete, token(authorization))

    @router.post("/test")
    def test(authorization: str | None = Header(None)):
        return run(manager.test, token(authorization))

    @router.post("/dispatch")
    def dispatch(dry_run: bool = Query(True), authorization: str | None = Header(None)):
        expected = settings.phone_job_token
        if not expected or not hmac.compare_digest(token(authorization), expected):
            raise HTTPException(401, "Scheduler access is required.")
        if not dry_run:
            raise HTTPException(409, "Notification delivery runs through the GitHub worker. Use dry-run here to preview matches.")
        return run(manager.dispatch, lambda: svc.refresh_current_portfolio(7),
                   lambda: svc.portfolio_queue(mode="live", window="7d"), dry_run=dry_run)

    return router
