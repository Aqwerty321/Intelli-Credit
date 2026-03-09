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
    demo_rank: Optional[int] = None
    demo_case_label: Optional[str] = None
    presentation_summary: Optional[dict] = None
    graph_expectations: Optional[dict] = None
    expected_artifacts: Optional[dict] = None


class CaseSummary(BaseModel):
    case_id: str
    company_name: str
    loan_amount: float
    loan_purpose: str
    sector: str = ""
    location: str = ""
    status: str
    recommendation: Optional[str] = None
    risk_score: Optional[float] = None
    demo_rank: Optional[int] = None
    demo_case_label: Optional[str] = None
    presentation_summary: Optional[dict] = None
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
        "demo_rank": payload.demo_rank,
        "demo_case_label": payload.demo_case_label,
        "presentation_summary": payload.presentation_summary,
        "graph_expectations": payload.graph_expectations,
        "expected_artifacts": payload.expected_artifacts,
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
    trace_files = sorted(case_dir.glob("*_trace.json"))
    if trace_files:
        with open(trace_files[-1]) as f:
            meta["trace"] = json.load(f)

    # Attach research findings
    research_files = sorted(case_dir.glob("*_research.json"))
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
    meta["documents"] = sorted(f.name for f in docs_dir.iterdir() if not f.name.startswith("."))

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


@router.get("/stats/dashboard")
def dashboard_stats():
    """Aggregate portfolio statistics for the dashboard."""
    cases = []
    for d in sorted(CASES_DIR.iterdir(), reverse=True):
        meta_file = d / "meta.json"
        if not meta_file.exists():
            continue
        try:
            with open(meta_file) as f:
                cases.append(json.load(f))
        except Exception:
            pass

    total = len(cases)
    completed = [c for c in cases if c.get("status") == "complete"]
    decision_counts = {"APPROVE": 0, "CONDITIONAL": 0, "REJECT": 0}
    risk_scores = []
    sector_counts = {}
    rule_counts = {}
    recent_activity = []

    for c in cases:
        rec = c.get("recommendation")
        if rec in decision_counts:
            decision_counts[rec] += 1
        rs = c.get("risk_score")
        if rs is not None:
            risk_scores.append(float(rs))
        sector = c.get("sector") or "Unknown"
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        recent_activity.append({
            "case_id": c["case_id"],
            "company_name": c.get("company_name", ""),
            "action": c.get("status", "created"),
            "recommendation": rec,
            "risk_score": rs,
            "timestamp": c.get("updated_at") or c.get("created_at", ""),
        })

    # Load rule firings from traces
    for c in completed:
        case_dir = _case_dir(c["case_id"])
        trace_files = sorted(case_dir.glob("*_trace.json"))
        if trace_files:
            try:
                with open(trace_files[-1]) as f:
                    trace = json.load(f)
                for rf in trace.get("rule_firings", []):
                    slug = rf.get("rule_slug", rf.get("rule_id", "unknown"))
                    rule_counts[slug] = rule_counts.get(slug, 0) + 1
            except Exception:
                pass

    # Risk distribution (5 buckets)
    risk_distribution = [
        {"range": "0.0 – 0.2", "count": sum(1 for r in risk_scores if r < 0.2)},
        {"range": "0.2 – 0.4", "count": sum(1 for r in risk_scores if 0.2 <= r < 0.4)},
        {"range": "0.4 – 0.6", "count": sum(1 for r in risk_scores if 0.4 <= r < 0.6)},
        {"range": "0.6 – 0.8", "count": sum(1 for r in risk_scores if 0.6 <= r < 0.8)},
        {"range": "0.8 – 1.0", "count": sum(1 for r in risk_scores if r >= 0.8)},
    ]

    avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else None

    # Recent activity sorted newest first, capped at 20
    recent_activity.sort(key=lambda x: x["timestamp"], reverse=True)
    recent_activity = recent_activity[:20]

    return {
        "total_cases": total,
        "completed_cases": len(completed),
        "decision_counts": decision_counts,
        "avg_risk": round(avg_risk, 4) if avg_risk is not None else None,
        "risk_distribution": risk_distribution,
        "sector_breakdown": [{"sector": k, "count": v} for k, v in sorted(sector_counts.items(), key=lambda x: -x[1])],
        "top_rules_fired": [{"rule": k, "count": v} for k, v in sorted(rule_counts.items(), key=lambda x: -x[1])[:10]],
        "recent_activity": recent_activity,
    }


@router.get("/compare/bulk")
def compare_cases(ids: str):
    """Return summary + trace data for multiple cases for side-by-side comparison.

    Query: ?ids=case_abc,case_def,case_ghi (up to 5)
    """
    case_ids = [cid.strip() for cid in ids.split(",") if cid.strip()]
    if not case_ids:
        raise HTTPException(400, "Provide at least one case id via ?ids=")
    if len(case_ids) > 5:
        raise HTTPException(400, "Compare at most 5 cases at a time")

    results = []
    for cid in case_ids:
        meta = _load_meta(cid)
        case_dir = _case_dir(cid)

        # Attach trace summary
        trace_summary = {}
        trace_files = sorted(case_dir.glob("*_trace.json"))
        if trace_files:
            try:
                with open(trace_files[-1]) as f:
                    trace = json.load(f)
                decision = trace.get("decision", {})
                trace_summary = {
                    "recommendation": decision.get("recommendation"),
                    "risk_score": decision.get("risk_score"),
                    "recommended_amount": decision.get("recommended_amount"),
                    "rules_fired_count": trace.get("rules_fired_count", 0),
                    "rule_firings": trace.get("rule_firings", []),
                    "graph_trace": {
                        "node_count": trace.get("graph_trace", {}).get("node_count", 0),
                        "edge_count": trace.get("graph_trace", {}).get("edge_count", 0),
                        "suspicious_cycles": trace.get("graph_trace", {}).get("suspicious_cycles", 0),
                        "gnn_label": trace.get("graph_trace", {}).get("gnn_label", "clean"),
                        "gnn_risk_score": trace.get("graph_trace", {}).get("gnn_risk_score", 0),
                        "fraud_alerts": trace.get("graph_trace", {}).get("fraud_alerts", []),
                    },
                    "evidence_judge": trace.get("evidence_judge", {}),
                    "schema_version": trace.get("schema_version"),
                }
            except Exception:
                pass

        results.append({
            "case_id": cid,
            "company_name": meta.get("company_name", ""),
            "loan_amount": meta.get("loan_amount", 0),
            "loan_purpose": meta.get("loan_purpose", ""),
            "sector": meta.get("sector", ""),
            "status": meta.get("status", ""),
            "created_at": meta.get("created_at", ""),
            **trace_summary,
        })

    return results


@router.get("/{case_id}/cam")
def download_cam(case_id: str):
    """Download the generated CAM markdown file."""
    case_dir = _case_dir(case_id)
    cam_files = sorted(case_dir.glob("cam_*.md"))
    if not cam_files:
        raise HTTPException(404, "CAM not yet generated for this case")
    return FileResponse(
        str(cam_files[-1]),
        media_type="text/markdown",
        filename=f"CAM_{case_id}.md",
    )


@router.get("/{case_id}/cam/pdf")
def download_cam_pdf(case_id: str):
    """Generate and download the CAM as a professional PDF."""
    meta = _load_meta(case_id)
    case_dir = _case_dir(case_id)

    # Load trace data for the PDF
    trace = {}
    trace_files = sorted(case_dir.glob("*_trace.json"))
    if trace_files:
        with open(trace_files[-1]) as f:
            trace = json.load(f)

    decision = trace.get("decision", {})
    graph_trace = trace.get("graph_trace", {})
    rule_firings = trace.get("rule_firings", [])
    evidence_judge = trace.get("evidence_judge", {})

    from services.cam.pdf_generator import generate_cam_pdf
    pdf_path = case_dir / f"CAM_{case_id}.pdf"
    generate_cam_pdf(
        output_path=str(pdf_path),
        company_name=meta.get("company_name", ""),
        loan_amount=meta.get("loan_amount", 0),
        loan_purpose=meta.get("loan_purpose", ""),
        sector=meta.get("sector", ""),
        recommendation=decision.get("recommendation", meta.get("recommendation", "PENDING")),
        risk_score=decision.get("risk_score", meta.get("risk_score", 0)),
        recommended_amount=decision.get("recommended_amount", 0),
        rule_firings=rule_firings,
        graph_trace=graph_trace,
        evidence_judge=evidence_judge,
        trace=trace,
    )

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=f"CAM_{meta.get('company_name', case_id).replace(' ', '_')}.pdf",
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


# ---------------------------------------------------------------------------
# Graph Topology & Features
# ---------------------------------------------------------------------------

def _load_graph_trace(case_id: str) -> dict:
    """Load graph_trace from the latest trace file for a case."""
    case_dir = _case_dir(case_id)
    trace_files = sorted(case_dir.glob("*_trace.json"))
    if not trace_files:
        raise HTTPException(404, "No analysis run found for this case — run the pipeline first")
    with open(trace_files[-1]) as f:
        trace = json.load(f)
    graph_trace = trace.get("graph_trace")
    if not graph_trace:
        raise HTTPException(404, "No graph data in trace — the pipeline may not have produced graph evidence")
    return graph_trace


@router.get("/{case_id}/graph")
def get_case_graph(case_id: str):
    """Return full graph topology (nodes, edges, fraud alerts, GNN inference) for D3 visualization."""
    _load_meta(case_id)
    graph_trace = _load_graph_trace(case_id)

    topology = graph_trace.get("graph_topology", {"nodes": [], "edges": []})
    return {
        "case_id": case_id,
        "node_count": graph_trace.get("node_count", 0),
        "edge_count": graph_trace.get("edge_count", 0),
        "nodes": topology.get("nodes", []),
        "edges": topology.get("edges", []),
        "fraud_alerts": graph_trace.get("fraud_alerts", []),
        "gnn_label": graph_trace.get("gnn_label", "clean"),
        "gnn_risk_score": graph_trace.get("gnn_risk_score", 0.0),
        "class_probabilities": graph_trace.get("class_probabilities", {}),
        "top_entities": graph_trace.get("top_entities", []),
        "visual_ready": graph_trace.get("visual_ready", False),
    }


@router.get("/{case_id}/graph/features")
def get_case_graph_features(case_id: str):
    """Return raw GNN feature vectors and edge index for frontend ONNX inference."""
    _load_meta(case_id)
    graph_trace = _load_graph_trace(case_id)

    transactions = graph_trace.get("graph_transactions", [])
    if not transactions:
        return {
            "case_id": case_id,
            "node_count": 0,
            "feature_dim": 7,
            "node_names": [],
            "features": [],
            "edge_index": [[], []],
        }

    # Re-compute features from stored transactions
    from services.graph.intelligence import _transactions_to_data, ROLE_TO_VALUE
    data = _transactions_to_data(transactions)
    return {
        "case_id": case_id,
        "node_count": int(data.x.shape[0]),
        "feature_dim": int(data.x.shape[1]),
        "node_names": data.node_names,
        "features": data.x.tolist(),
        "edge_index": data.edge_index.tolist(),
        "edge_weights": data.edge_weight.tolist() if hasattr(data, "edge_weight") else [],
        "role_to_value": ROLE_TO_VALUE,
    }
