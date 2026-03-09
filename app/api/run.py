"""
Run API: trigger pipeline execution with SSE progress streaming.
GET /api/run/{case_id}/stream  — SSE stream of progress events
POST /api/run/{case_id}        — synchronous run (for CI/testing)
"""
import json
import asyncio
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CASES_DIR = PROJECT_ROOT / "storage" / "cases"

router = APIRouter()


def _emit(queue: asyncio.Queue, event: str, data: dict):
    """Thread-safe SSE event emitter."""
    queue.put_nowait({"event": event, "data": json.dumps(data)})


def _run_pipeline_thread(case_id: str, meta: dict, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    """Run the full pipeline in a background thread, emitting SSE progress events."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))

    def emit(event: str, data: dict):
        asyncio.run_coroutine_threadsafe(queue.put({"event": event, "data": json.dumps(data)}), loop)

    try:
        case_dir = CASES_DIR / case_id
        docs_dir = case_dir / "docs"
        input_files = [str(f) for f in docs_dir.iterdir() if not f.name.startswith(".")]

        if not input_files:
            emit("error", {"message": "No documents uploaded for this case"})
            return

        emit("progress", {"phase": "ingestion", "message": f"Processing {len(input_files)} document(s)"})

        # Research phase
        emit("progress", {"phase": "research", "message": "Running secondary research..."})
        research_findings = []
        try:
            from services.agents.research_router import ResearchRouterAgent
            from services.agents.research_agent import ResearchAgent
            agent = ResearchAgent()
            company_profile = {
                "name": meta.get("company_name", ""),
                "sector": meta.get("sector", ""),
                "location": meta.get("location", ""),
                "promoters": meta.get("promoters", []),
                "known_facts": [],
            }
            # P2: generate research plan first, then use planned queries in execution
            planned_queries = None
            try:
                router = ResearchRouterAgent()
                plan = router.plan(company_profile, risk_hints=[])
                planned_queries = [q.query for q in plan.queries]
            except Exception:
                pass  # fallback: research_agent will generate its own queries
            result = agent.research_company(company_profile, use_cache=True,
                                            planned_queries=planned_queries)
            research_findings = result.get("findings", [])
            # Save research to case dir
            with open(case_dir / f"{case_id}_research.json", "w") as f:
                json.dump(result, f, indent=2)
            emit("research_complete", {
                "findings_count": len(research_findings),
                "negative_count": sum(1 for f in research_findings if f.get("risk_impact") == "negative"),
            })
        except Exception as e:
            emit("warning", {"message": f"Research failed (continuing): {e}"})

        emit("progress", {"phase": "reasoning", "message": "Running rule engine and LLM..."})

        # Load officer notes for context injection
        officer_notes = []
        notes_path = case_dir / "notes.json"
        if notes_path.exists():
            try:
                with open(notes_path) as f:
                    officer_notes = json.load(f)
            except Exception:
                pass

        # Run pipeline
        from services.pipeline import run_pipeline
        output_dir = str(case_dir)
        run_pipeline(
            input_files=input_files,
            company_name=meta["company_name"],
            loan_amount=meta["loan_amount"],
            loan_purpose=meta.get("loan_purpose", "Working Capital"),
            research_findings=research_findings,
            output_dir=output_dir,
            sector=meta.get("sector", ""),
            location=meta.get("location", ""),
            promoters=meta.get("promoters", []),
            officer_notes=officer_notes,
            case_meta=meta,
        )

        # Load generated trace
        trace_files = sorted(case_dir.glob("*_trace.json"))
        trace = {}
        if trace_files:
            with open(trace_files[-1]) as f:
                trace = json.load(f)

        # Update case meta with result
        meta_path = case_dir / "meta.json"
        with open(meta_path) as f:
            current_meta = json.load(f)
        decision = trace.get("decision", {})
        current_meta["status"] = "complete"
        current_meta["recommendation"] = decision.get("recommendation")
        current_meta["risk_score"] = decision.get("risk_score")
        current_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(meta_path, "w") as f:
            json.dump(current_meta, f, indent=2)

        # v3 supplemental events — emitted BEFORE complete so the Judge panel
        # is populated before the UI transitions out of the running state.
        if trace.get("schema_version") == "v3":
            if trace.get("research_plan"):
                rp = trace["research_plan"]
                emit("research_plan_ready", {
                    "queries": len(rp.get("queries", [])),
                    "focus_areas": rp.get("focus_areas", []),
                    "fallback": rp.get("fallback", True),
                })
            if trace.get("evidence_judge"):
                ej = trace["evidence_judge"]
                emit("evidence_scored", {
                    "accepted": ej.get("accepted", 0),
                    "rejected": ej.get("rejected", 0),
                    "precision_at_10": ej.get("precision_at_10"),
                    "corroboration_rate": ej.get("corroboration_rate"),
                })
            if trace.get("claim_graph"):
                cg = trace["claim_graph"]
                emit("claim_graph_ready", {
                    "claims": cg.get("claims_total", 0),
                    "corroborated": cg.get("corroborated", 0),
                    "contradictions": cg.get("contradictions", 0),
                })
            if trace.get("counterfactuals"):
                cf = trace["counterfactuals"]
                emit("counterfactual_ready", {
                    "scenarios": cf.get("scenario_count", 0),
                    "top_scenario": cf.get("top_scenario"),
                })

        emit("complete", {
            "recommendation": decision.get("recommendation"),
            "risk_score": decision.get("risk_score"),
            "rules_fired_count": len(trace.get("rule_firings", [])),
            "schema_version": trace.get("schema_version", "v3"),
        })

    except Exception as e:
        import traceback
        emit("error", {"message": str(e), "detail": traceback.format_exc()})


async def _sse_generator(queue: asyncio.Queue) -> AsyncGenerator[dict, None]:
    """Yield SSE events from the queue until the pipeline completes."""
    while True:
        item = await asyncio.wait_for(queue.get(), timeout=300.0)
        yield item
        if item["event"] in ("complete", "error"):
            break


@router.get("/{case_id}/stream")
async def run_stream(case_id: str):
    """
    SSE endpoint — streams pipeline progress for the browser.
    Connect with EventSource('/api/run/{case_id}/stream').
    """
    case_dir = CASES_DIR / case_id
    meta_path = case_dir / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404, f"Case {case_id} not found")
    with open(meta_path) as f:
        meta = json.load(f)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(case_id, meta, queue, loop),
        daemon=True,
    )
    thread.start()

    return EventSourceResponse(_sse_generator(queue))


@router.post("/{case_id}")
def run_sync(case_id: str):
    """
    Synchronous pipeline run (used by CLI and acceptance tests).
    Blocks until complete.
    """
    case_dir = CASES_DIR / case_id
    meta_path = case_dir / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404, f"Case {case_id} not found")
    with open(meta_path) as f:
        meta = json.load(f)

    docs_dir = case_dir / "docs"
    input_files = [str(f) for f in docs_dir.iterdir() if not f.name.startswith(".")]
    if not input_files:
        raise HTTPException(400, "No documents uploaded for this case")

    research_findings = []
    try:
        from services.agents.research_agent import ResearchAgent
        agent = ResearchAgent()
        company_profile = {
            "name": meta.get("company_name", ""),
            "sector": meta.get("sector", ""),
            "location": meta.get("location", ""),
            "promoters": meta.get("promoters", []),
            "known_facts": [],
        }
        result = agent.research_company(company_profile, use_cache=True)
        research_findings = result.get("findings", [])
        with open(case_dir / f"{case_id}_research.json", "w") as f:
            json.dump(result, f, indent=2)
    except Exception as e:
        print(f"Research failed (continuing): {e}")

    from services.pipeline import run_pipeline
    officer_notes = []
    notes_path = case_dir / "notes.json"
    if notes_path.exists():
        try:
            with open(notes_path) as f:
                officer_notes = json.load(f)
        except Exception:
            pass
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
        officer_notes=officer_notes,
        case_meta=meta,
    )

    # Load trace
    trace_files = sorted(case_dir.glob("*_trace.json"))
    trace = {}
    if trace_files:
        with open(trace_files[-1]) as f:
            trace = json.load(f)

    # Update meta
    decision = trace.get("decision", {})
    meta["status"] = "complete"
    meta["recommendation"] = decision.get("recommendation")
    meta["risk_score"] = decision.get("risk_score")
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return {
        "case_id": case_id,
        "recommendation": decision.get("recommendation"),
        "risk_score": decision.get("risk_score"),
        "rules_fired_count": len(trace.get("rule_firings", [])),
        "schema_version": trace.get("schema_version", "v2"),
    }
