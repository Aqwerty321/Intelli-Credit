"""
Intelli-Credit FastAPI backend.
Serves the full credit appraisal workflow via REST + SSE.
"""
import json
import os
import re
import shutil
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.cases import router as cases_router, CASES_DIR
from app.api.run import router as run_router
from app.api.autofetch import router as autofetch_router

SEED_DIR = PROJECT_ROOT / "demo" / "seed"
INTEL_DIR = PROJECT_ROOT / "demo" / "intelligence_cases"
CACHE_DIR = PROJECT_ROOT / "storage" / "cache" / "research"

# Map seed case_label → intelligence_cases folder name
_LABEL_TO_FOLDER = {
    "APPROVE": "approve",
    "CONDITIONAL": "conditional",
    "REJECT": "reject",
}


def _sanitize_name(name: str) -> str:
    return re.sub(r'[^\w]', '_', name.lower())[:60]


def _seed_demo_cases():
    """Create demo cases from demo/seed/*.json with full documents + pipeline run."""
    if not SEED_DIR.exists():
        return

    # Index existing cases by company name → (case_dir, meta)
    existing: dict[str, tuple[Path, dict]] = {}
    if CASES_DIR.exists():
        for d in CASES_DIR.iterdir():
            meta_file = d / "meta.json"
            if meta_file.exists():
                try:
                    with open(meta_file) as f:
                        m = json.load(f)
                    name = m.get("company_name", "")
                    if name:
                        existing[name] = (d, m)
                except Exception:
                    pass

    cases_to_run: list[tuple[str, str, dict]] = []  # (case_id, case_label, meta)

    for seed_file in sorted(SEED_DIR.glob("*.json")):
        try:
            with open(seed_file) as f:
                seed = json.load(f)
            company_name = seed.get("company_name", "")
            case_label = seed.get("case_label", "")
            if not company_name:
                continue

            # Check if case already exists AND has been run (complete)
            if company_name in existing:
                prev_dir, prev_meta = existing[company_name]
                if prev_meta.get("status") == "complete":
                    continue  # already fully set up
                # Exists but incomplete — upgrade it with docs + pipeline
                case_id = prev_meta["case_id"]
                case_dir = prev_dir
                meta = prev_meta
            else:
                # Create fresh case
                case_id = f"case_{uuid.uuid4().hex[:12]}"
                case_dir = CASES_DIR / case_id
                case_dir.mkdir(parents=True, exist_ok=True)
                now = datetime.now(timezone.utc).isoformat()
                meta = {
                    "case_id": case_id,
                    "company_name": company_name,
                    "loan_amount": seed.get("loan_amount", 0),
                    "loan_purpose": seed.get("loan_purpose", "Working Capital"),
                    "sector": seed.get("sector", ""),
                    "location": seed.get("location", ""),
                    "promoters": seed.get("promoters", []),
                    "status": "created",
                    "recommendation": None,
                    "risk_score": None,
                    "demo_rank": None,
                    "demo_case_label": case_label,
                    "created_at": now,
                    "updated_at": now,
                }
                with open(case_dir / "meta.json", "w") as f:
                    json.dump(meta, f, indent=2)
                print(f"  [Seed] Created demo case: {company_name} ({case_id})")

            docs_dir = case_dir / "docs"
            docs_dir.mkdir(exist_ok=True)

            # Copy documents from intelligence_cases if available
            folder_name = _LABEL_TO_FOLDER.get(case_label, "")
            intel_folder = INTEL_DIR / folder_name if folder_name else None
            if intel_folder and intel_folder.exists():
                for doc_name in ("facts.md", "transactions.json"):
                    src = intel_folder / doc_name
                    if src.exists():
                        shutil.copy2(src, docs_dir / doc_name)

                # Place research cache
                cache_src = intel_folder / "research_cache.json"
                if cache_src.exists():
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    safe = _sanitize_name(company_name)
                    shutil.copy2(cache_src, CACHE_DIR / f"{safe}_v3_research.json")
                    shutil.copy2(cache_src, case_dir / f"{case_id}_research.json")

            cases_to_run.append((case_id, case_label, meta))
        except Exception as e:
            print(f"  [Seed] Failed to seed {seed_file.name}: {e}")

    # Run pipeline for each seeded case so they have full analytics
    if cases_to_run:
        try:
            from services.pipeline import run_pipeline
        except Exception as e:
            print(f"  [Seed] Cannot import pipeline: {e}")
            return

        for case_id, case_label, meta in cases_to_run:
            case_dir = CASES_DIR / case_id
            docs_dir = case_dir / "docs"
            input_files = [str(f) for f in docs_dir.iterdir() if not f.name.startswith(".")]
            if not input_files:
                print(f"  [Seed] Skipping pipeline for {meta['company_name']} — no docs")
                continue

            # Load research if placed
            research_findings = []
            research_file = case_dir / f"{case_id}_research.json"
            if research_file.exists():
                try:
                    with open(research_file) as f:
                        research_findings = json.load(f).get("findings", [])
                except Exception:
                    pass

            try:
                print(f"  [Seed] Running pipeline for {meta['company_name']}...")
                run_pipeline(
                    input_files=input_files,
                    company_name=meta["company_name"],
                    loan_amount=meta["loan_amount"],
                    loan_purpose=meta.get("loan_purpose", "Working Capital"),
                    research_findings=research_findings,
                    output_dir=str(case_dir),
                    sector=meta.get("sector", ""),
                    location=meta.get("location", ""),
                    promoters=meta.get("promoters", []),
                    officer_notes=[],
                    case_meta=meta,
                )
                # Update meta with results
                trace_files = sorted(case_dir.glob("*_trace.json"))
                if trace_files:
                    with open(trace_files[-1]) as f:
                        trace = json.load(f)
                    decision = trace.get("decision", {})
                    meta["status"] = "complete"
                    meta["recommendation"] = decision.get("recommendation")
                    meta["risk_score"] = decision.get("risk_score")
                    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                    with open(case_dir / "meta.json", "w") as f:
                        json.dump(meta, f, indent=2)
                    print(f"  [Seed] {meta['company_name']}: {meta['recommendation']} "
                          f"(risk={meta['risk_score']})")
            except Exception as e:
                print(f"  [Seed] Pipeline failed for {meta['company_name']}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_demo_cases()
    yield


app = FastAPI(
    title="Intelli-Credit API",
    description="AI-powered credit decisioning engine",
    version="3.0.0",
    lifespan=lifespan,
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
