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

    # Attach officer notes
    notes_path = case_dir / "notes.json"
    if notes_path.exists():
        try:
            with open(notes_path) as f:
                meta["officer_notes"] = [_normalize_note_record(n) for n in json.load(f)]
        except Exception:
            meta["officer_notes"] = []
    else:
        meta["officer_notes"] = []

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


# ---------------------------------------------------------------------------
# Officer Notes
# ---------------------------------------------------------------------------

def _normalize_tags(tags: list) -> list:
    """Lowercase, strip, deduplicate, limit to 5 tags."""
    seen = {}
    for t in tags:
        cleaned = str(t).lower().strip()
        if cleaned:
            seen[cleaned] = None
    return list(seen.keys())[:5]


def _normalize_note_record(raw: dict) -> dict:
    """Back-fill fields missing from legacy notes that predate Notes 2.0."""
    raw.setdefault("tags", [])
    raw.setdefault("pinned", False)
    raw.setdefault("updated_at", raw.get("created_at", ""))
    return raw


class OfficerNote(BaseModel):
    author: str
    text: str
    note_type: str = "general"   # "general" | "risk" | "approval" | "escalation"
    tags: list[str] = []
    pinned: bool = False


class OfficerNoteRecord(BaseModel):
    note_id: str
    author: str
    text: str
    note_type: str
    created_at: str
    updated_at: str = ""
    tags: list[str] = []
    pinned: bool = False


class NoteUpdate(BaseModel):
    text: Optional[str] = None
    note_type: Optional[str] = None
    tags: Optional[list[str]] = None
    pinned: Optional[bool] = None


@router.post("/{case_id}/notes", status_code=201, response_model=OfficerNoteRecord)
def add_officer_note(case_id: str, note: OfficerNote):
    """Add a credit-officer note to a case."""
    _load_meta(case_id)
    notes_path = _case_dir(case_id) / "notes.json"

    notes: list[dict] = []
    if notes_path.exists():
        with open(notes_path) as f:
            notes = json.load(f)

    now = datetime.now(timezone.utc).isoformat()
    record = OfficerNoteRecord(
        note_id=f"note_{uuid.uuid4().hex[:8]}",
        author=note.author,
        text=note.text,
        note_type=note.note_type,
        created_at=now,
        updated_at=now,
        tags=_normalize_tags(note.tags),
        pinned=note.pinned,
    )
    notes.append(record.model_dump())
    with open(notes_path, "w") as f:
        json.dump(notes, f, indent=2)

    return record


@router.get("/{case_id}/notes", response_model=list[OfficerNoteRecord])
def get_officer_notes(case_id: str):
    """Retrieve all officer notes for a case."""
    _load_meta(case_id)   # validates case exists
    notes_path = _case_dir(case_id) / "notes.json"
    if not notes_path.exists():
        return []
    with open(notes_path) as f:
        raw_notes = json.load(f)
    return [_normalize_note_record(n) for n in raw_notes]


@router.patch("/{case_id}/notes/{note_id}", response_model=OfficerNoteRecord)
def update_officer_note(case_id: str, note_id: str, patch: NoteUpdate):
    """Partially update an officer note (text, note_type, tags, pinned)."""
    _load_meta(case_id)
    notes_path = _case_dir(case_id) / "notes.json"
    if not notes_path.exists():
        raise HTTPException(404, f"Note {note_id} not found")

    with open(notes_path) as f:
        notes = json.load(f)

    idx = next((i for i, n in enumerate(notes) if n.get("note_id") == note_id), None)
    if idx is None:
        raise HTTPException(404, f"Note {note_id} not found")

    note = _normalize_note_record(notes[idx])
    if patch.text is not None:
        note["text"] = patch.text
    if patch.note_type is not None:
        note["note_type"] = patch.note_type
    if patch.tags is not None:
        note["tags"] = _normalize_tags(patch.tags)
    if patch.pinned is not None:
        note["pinned"] = patch.pinned
    note["updated_at"] = datetime.now(timezone.utc).isoformat()

    notes[idx] = note
    with open(notes_path, "w") as f:
        json.dump(notes, f, indent=2)

    return note


@router.delete("/{case_id}/notes/{note_id}", status_code=204)
def delete_officer_note(case_id: str, note_id: str):
    """Delete a single officer note."""
    _load_meta(case_id)
    notes_path = _case_dir(case_id) / "notes.json"
    if not notes_path.exists():
        raise HTTPException(404, f"Note {note_id} not found")

    with open(notes_path) as f:
        notes = json.load(f)

    filtered = [n for n in notes if n.get("note_id") != note_id]
    if len(filtered) == len(notes):
        raise HTTPException(404, f"Note {note_id} not found")

    with open(notes_path, "w") as f:
        json.dump(filtered, f, indent=2)
