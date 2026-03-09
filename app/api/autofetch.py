"""
AutoFetch API: research a company via SearXNG + LLM and generate facts.md.

GET  /api/cases/{case_id}/autofetch/check   — check if facts.md already exists
GET  /api/cases/{case_id}/autofetch/stream   — SSE stream of autofetch progress
"""
import json
import asyncio
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CASES_DIR = PROJECT_ROOT / "storage" / "cases"

router = APIRouter()


def _load_meta(case_id: str) -> dict:
    meta_path = CASES_DIR / case_id / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404, f"Case {case_id} not found")
    with open(meta_path) as f:
        return json.load(f)


def _save_meta(case_id: str, meta: dict):
    meta_path = CASES_DIR / case_id / "meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)


@router.get("/{case_id}/check")
def check_facts(case_id: str):
    """Check if facts.md already exists in the case docs."""
    meta = _load_meta(case_id)
    docs_dir = CASES_DIR / case_id / "docs"
    facts_exists = (docs_dir / "facts.md").exists()
    return {"facts_exists": facts_exists, "case_id": case_id}


def _emit(queue, event: str, data: dict, loop):
    """Thread-safe SSE event emitter."""
    asyncio.run_coroutine_threadsafe(
        queue.put({"event": event, "data": json.dumps(data)}), loop
    )


def _autofetch_thread(case_id: str, meta: dict, force: bool,
                      queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    """Run research + facts generation in a background thread with SSE progress."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))

    def emit(event: str, data: dict):
        _emit(queue, event, data, loop)

    try:
        case_dir = CASES_DIR / case_id
        docs_dir = case_dir / "docs"
        facts_path = docs_dir / "facts.md"

        # Check overwrite
        if facts_path.exists() and not force:
            emit("confirm_overwrite", {
                "message": "facts.md already exists. Re-open with ?force=true to overwrite.",
            })
            emit("error", {"message": "facts.md already exists. Use force=true to overwrite."})
            return

        company_name = meta.get("company_name", "Unknown")
        emit("progress", {"phase": "autofetch", "message": f"Starting AutoFetch for {company_name}…"})

        # ── Step 1: Plan research queries ──────────────────────────────────
        emit("progress", {"phase": "planning", "message": "Planning research queries…"})
        planned_queries = None
        plan_meta = {}
        try:
            from services.agents.research_router import ResearchRouterAgent
            router_agent = ResearchRouterAgent()
            company_profile = {
                "name": company_name,
                "sector": meta.get("sector", ""),
                "location": meta.get("location", ""),
                "promoters": meta.get("promoters", []),
                "known_facts": [],
            }
            plan = router_agent.plan(company_profile, risk_hints=[])
            planned_queries = [q.query for q in plan.queries]
            plan_meta = {
                "queries": len(planned_queries),
                "focus_areas": plan.focus_areas,
                "fallback": plan.fallback,
            }
            emit("progress", {
                "phase": "planning",
                "message": f"Research plan ready: {len(planned_queries)} queries, focus: {', '.join(plan.focus_areas[:3])}",
            })
        except Exception as e:
            emit("progress", {"phase": "planning", "message": f"Router fallback (deterministic queries): {e}"})

        # ── Step 2: Execute research ───────────────────────────────────────
        emit("progress", {"phase": "research", "message": "Searching the web via SearXNG…"})
        company_profile = {
            "name": company_name,
            "sector": meta.get("sector", ""),
            "location": meta.get("location", ""),
            "promoters": meta.get("promoters", []),
            "loan_amount": meta.get("loan_amount", ""),
            "loan_purpose": meta.get("loan_purpose", ""),
            "known_facts": [],
        }

        from services.agents.research_agent import ResearchAgent
        agent = ResearchAgent()
        research_result = agent.research_company(
            company_profile, use_cache=True, planned_queries=planned_queries,
        )
        findings = research_result.get("findings", [])
        neg_count = sum(1 for f in findings if f.get("risk_impact") == "negative")

        # Save research to case dir
        research_path = case_dir / f"{case_id}_research.json"
        with open(research_path, "w") as f:
            json.dump(research_result, f, indent=2)

        emit("research_complete", {
            "findings_count": len(findings),
            "negative_count": neg_count,
            "queries_executed": research_result.get("queries_executed", 0),
            "elapsed_seconds": research_result.get("elapsed_seconds", 0),
        })

        # ── Step 3: Generate facts.md ──────────────────────────────────────
        emit("progress", {"phase": "synthesis", "message": "Generating facts document…"})

        from services.agents.facts_generator import FactsGenerator
        generator = FactsGenerator()

        def progress_cb(msg):
            emit("progress", {"phase": "synthesis", "message": msg})

        company_data = {
            "name": company_name,
            "sector": meta.get("sector", ""),
            "location": meta.get("location", ""),
            "loan_amount": meta.get("loan_amount", 0),
            "loan_purpose": meta.get("loan_purpose", "Working Capital"),
            "promoters": meta.get("promoters", []),
        }
        content, gen_meta = generator.generate(company_data, findings, progress_cb=progress_cb)

        # ── Step 4: Save facts.md ──────────────────────────────────────────
        docs_dir.mkdir(parents=True, exist_ok=True)
        with open(facts_path, "w") as f:
            f.write(content)

        # Update case meta
        meta["status"] = "documents_uploaded"
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_meta(case_id, meta)

        emit("progress", {"phase": "synthesis", "message": f"facts.md saved ({len(content)} chars)"})

        emit("complete", {
            "filename": "facts.md",
            "findings_count": len(findings),
            "negative_count": neg_count,
            "generation_method": gen_meta.get("method", "unknown"),
            "size_bytes": len(content.encode()),
        })

    except Exception as e:
        import traceback
        emit("error", {"message": str(e), "detail": traceback.format_exc()})


async def _sse_generator(queue: asyncio.Queue):
    """Yield SSE events until complete or error."""
    while True:
        item = await asyncio.wait_for(queue.get(), timeout=300.0)
        yield item
        if item["event"] in ("complete", "error"):
            break


@router.get("/{case_id}/stream")
async def autofetch_stream(case_id: str, force: bool = Query(False)):
    """
    SSE endpoint — streams autofetch progress.
    Connect with EventSource('/api/autofetch/{case_id}/stream?force=true').
    """
    meta = _load_meta(case_id)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    thread = threading.Thread(
        target=_autofetch_thread,
        args=(case_id, meta, force, queue, loop),
        daemon=True,
    )
    thread.start()

    return EventSourceResponse(_sse_generator(queue))
