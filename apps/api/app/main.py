from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import tools as tools_router
from app.routers import active_learning as active_learning_router

logger = logging.getLogger("mangrove_ai")

ALLOWED_ORIGINS = ["http://localhost:3000"]

app = FastAPI(title="Mangrove AI Intelligence API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """A handler registered for the bare Exception class becomes
    ServerErrorMiddleware's error_handler in Starlette, not
    ExceptionMiddleware's — so it runs OUTSIDE CORSMiddleware and its
    response never passes through CORSMiddleware's header-adding logic.
    Without the manual header set below, every unhandled exception (a bad
    aoi_id, a real GEE error, a DB hiccup) would 500 with zero
    Access-Control-Allow-Origin, and the browser reports a bare "Failed to
    fetch" with no way for the frontend to see what actually happened."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    origin = request.headers.get("origin")
    headers = {"Access-Control-Allow-Origin": origin} if origin in ALLOWED_ORIGINS else {}
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"}, headers=headers)


app.include_router(tools_router.router, prefix="/api/v1")
app.include_router(active_learning_router.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
