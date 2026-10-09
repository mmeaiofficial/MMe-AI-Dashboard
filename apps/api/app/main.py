from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .audit.router import router as audit_router
from .authz import engine as E
from .core.config import load_settings
from .core.db import engine
from .core.deps import public
from .modules.access.allocate import router as allocate_router
from .modules.access.router import router as access_router
from .modules.assistant.router import router as assistant_router
from .modules.identity.router import me_router, router as auth_router
from .modules.org.router import router as org_router
from .modules.pipeline.router import router as pipeline_router
from .modules.pipeline.tickets import router as tickets_router

settings = load_settings()  # raises ConfigError on unsafe production settings
log = logging.getLogger("mme")

app = FastAPI(
    title="MME OS API", version="0.1.0",
    docs_url="/api/docs" if not settings.is_production else None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware, allow_origins=[settings.web_origin], allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["content-type", "x-csrf-token", "x-request-id", "idempotency-key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    response = await call_next(request)
    response.headers["x-request-id"] = request.state.request_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    response.headers["cache-control"] = "no-store"
    if settings.cookie_secure:
        response.headers["strict-transport-security"] = "max-age=63072000; includeSubDomains"
    return response


@app.exception_handler(E.NotFound)
async def _nf(_: Request, __: E.NotFound):
    return JSONResponse({"error": {"code": "not_found", "message": "Not found."}}, status_code=404)


@app.exception_handler(E.Forbidden)
async def _fb(_: Request, __: E.Forbidden):
    return JSONResponse({"error": {"code": "forbidden", "message": "You don't have permission to do that."}}, status_code=403)


@app.exception_handler(E.EscalationDenied)
async def _esc(_: Request, exc: E.EscalationDenied):
    return JSONResponse({"error": {"code": "forbidden", "message": str(exc)}}, status_code=403)


api = APIRouter(prefix="/api/v1")


@api.get("/health", dependencies=[Depends(public)])
def health() -> dict:
    with engine.connect() as c:
        c.execute(text("select 1"))
    return {"ok": True}


api.include_router(auth_router)
api.include_router(me_router)
api.include_router(access_router)
api.include_router(allocate_router)
api.include_router(org_router)
api.include_router(audit_router)
api.include_router(assistant_router)
api.include_router(pipeline_router)
api.include_router(tickets_router)
app.include_router(api)
