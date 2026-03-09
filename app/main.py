"""
Intelli-Credit FastAPI backend.
Serves the full credit appraisal workflow via REST + SSE.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.cases import router as cases_router
from app.api.run import router as run_router
from app.api.autofetch import router as autofetch_router

app = FastAPI(
    title="Intelli-Credit API",
    description="AI-powered credit decisioning engine",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases_router, prefix="/api/cases", tags=["cases"])
app.include_router(run_router, prefix="/api/run", tags=["run"])
app.include_router(autofetch_router, prefix="/api/autofetch", tags=["autofetch"])


def _health_response():
    return {"status": "ok", "version": "3.0.0"}


@app.get("/api/health")
def health():
    return _health_response()


@app.get("/health")
def health_alias():
    """Top-level alias for /api/health — backward-compatible."""
    return _health_response()


# Serve the built frontend from frontend/dist/ if it exists
frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
