"""
Cases API: CRUD for credit appraisal cases.
Cases are stored as directories under storage/cases/{case_id}/.
"""
import json
import os
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CASES_DIR = PROJECT_ROOT / "storage" / "cases"
CASES_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CaseCreate(BaseModel):
    company_name: str
    loan_amount: float
    loan_purpose: str = "Working Capital"
    sector: str = ""
    location: str = ""
    promoters: list[dict] = []


class CaseSummary(BaseModel):
    case_id: str
    company_name: str
    loan_amount: float
    loan_purpose: str
    status: str
    recommendation: Optional[str] = None
    risk_score: Optional[float] = None
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _case_dir(case_id: str) -> Path:
    return CASES_DIR / case_id


def _load_meta(case_id: str) -> dict:
    meta_path = _case_dir(case_id) / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404, f"Case {case_id} not found")
    with open(meta_path) as f:
        return json.load(f)


def _save_meta(case_id: str, meta: dict):
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(_case_dir(case_id) / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[CaseSummary])
def list_cases():
    """List all cases, sorted newest first."""
    cases = []
    for d in sorted(CASES_DIR.iterdir(), reverse=True):
        meta_file = d / "meta.json"
        if not meta_file.exists():
            continue
        try:
            with open(meta_file) as f:
                meta = json.load(f)
            cases.append(CaseSummary(**meta))
        except Exception:
            pass
    return cases


@router.post("/", response_model=CaseSummary, status_code=201)
def create_case(payload: CaseCreate):
    """Create a new case."""
    case_id = f"case_{uuid.uuid4().hex[:12]}"
    case_dir = _case_dir(case_id)
    case_dir.mkdir(parents=True)
    (case_dir / "docs").mkdir()

    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "case_id": case_id,
        "company_name": payload.company_name,
        "loan_amount": payload.loan_amount,
        "loan_purpose": payload.loan_purpose,
        "sector": payload.sector,
        "location": payload.location,
        "promoters": payload.promoters,
        "status": "created",
        "recommendation": None,
        "risk_score": None,
        "created_at": now,
        "updated_at": now,
    }
    with open(case_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    return CaseSummary(**meta)


@router.get("/{case_id}")
def get_case(case_id: str):
    """Get full case details including trace and research findings."""
    meta = _load_meta(case_id)
    case_dir = _case_dir(case_id)

    # Attach trace if run
    trace_files = list(case_dir.glob("*_trace.json"))
    if trace_files:
        with open(trace_files[-1]) as f:
            meta["trace"] = json.load(f)

    # Attach research findings
    research_files = list(case_dir.glob("*_research.json"))
    if research_files:
        with open(research_files[-1]) as f:
            meta["research"] = json.load(f)

    # List uploaded docs
    docs_dir = case_dir / "docs"
    meta["documents"] = [f.name for f in docs_dir.iterdir() if not f.name.startswith(".")]

    return meta


@router.post("/{case_id}/documents")
async def upload_document(case_id: str, file: UploadFile = File(...)):
    """Upload a document (PDF, JSON, TXT, MD) to a case."""
    meta = _load_meta(case_id)
    docs_dir = _case_dir(case_id) / "docs"

    # Validate extension
    allowed = {".pdf", ".json", ".txt", ".md"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported file type: {suffix}. Allowed: {allowed}")

    dest = docs_dir / file.filename
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    meta["status"] = "documents_uploaded"
    _save_meta(case_id, meta)

    return {"case_id": case_id, "filename": file.filename, "size": len(content)}


@router.get("/{case_id}/cam")
def download_cam(case_id: str):
    """Download the generated CAM markdown file."""
    case_dir = _case_dir(case_id)
    cam_files = list(case_dir.glob("cam_*.md"))
    if not cam_files:
        raise HTTPException(404, "CAM not yet generated for this case")
    return FileResponse(
        str(cam_files[-1]),
        media_type="text/markdown",
        filename=f"CAM_{case_id}.md",
    )


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: str):
    """Delete a case and all its files."""
    case_dir = _case_dir(case_id)
    if not case_dir.exists():
        raise HTTPException(404, f"Case {case_id} not found")
    shutil.rmtree(case_dir)
