from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import tools as tools_router
from app.routers import active_learning as active_learning_router

app = FastAPI(title="Mangrove AI Intelligence API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tools_router.router, prefix="/api/v1")
app.include_router(active_learning_router.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
