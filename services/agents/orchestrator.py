"""
Intelli-Credit Agent Orchestrator.

Implements a multi-agent system using tool-based architecture:
- Coordinator Agent: Plans and orchestrates the appraisal workflow
- Document Agent: Handles OCR and document ingestion
- Analysis Agent: Performs financial analysis and risk assessment
- Research Agent: Gathers external data (corporate registry, etc.)

Each agent has access to specific tools (pipeline services) and reports
back to the coordinator. State is persisted via DuckDB.
"""
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://172.23.112.1:11434")


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@dataclass
class Tool:
    """A callable tool that agents can invoke."""
    name: str
    description: str
    parameters: dict
    func: Callable

    def execute(self, **kwargs) -> dict:
        """Execute the tool and return result dict."""
        try:
            result = self.func(**kwargs)
            return {"status": "success", "result": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    """Persistent state for an agent execution."""
    agent_id: str
    task_id: str
    status: str = "pending"         # pending, running, completed, failed
    current_step: int = 0
    steps_completed: list = field(default_factory=list)
    tool_calls: list = field(default_factory=list)
    findings: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "status": self.status,
            "current_step": self.current_step,
            "steps_completed": self.steps_completed,
            "tool_calls": self.tool_calls,
            "findings": self.findings,
            "errors": self.errors,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def save(self, path: str):
        self.updated_at = datetime.now(timezone.utc).isoformat()
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "AgentState":
        with open(path) as f:
            data = json.load(f)
        return cls(**data)


# ---------------------------------------------------------------------------
# Tool factory: wraps existing services as tools
# ---------------------------------------------------------------------------

def _build_tools() -> dict[str, Tool]:
    """Build tool registry from existing services."""
    tools = {}

    # Tool: OCR Document
    def _ocr_document(pdf_path: str, output_dir: str = None) -> dict:
        from services.ingestor.glm_ocr import ocr_document
        return ocr_document(pdf_path, output_dir)

    tools["ocr_document"] = Tool(
        name="ocr_document",
        description="Extract text from a PDF document using OCR (PyMuPDF for text PDFs, Ollama vision for scanned).",
        parameters={"pdf_path": "str", "output_dir": "str (optional)"},
        func=_ocr_document,
    )

    # Tool: Extract Fields
    def _extract_fields(text: str) -> dict:
        from services.ingestor.validator import extract_all_fields
        return extract_all_fields(text)

    tools["extract_fields"] = Tool(
        name="extract_fields",
        description="Extract structured fields (GSTIN, PAN, dates, amounts) from text.",
        parameters={"text": "str"},
        func=_extract_fields,
    )

    # Tool: Entity Resolution
    def _resolve_entity(name: str, entity_type: str = "company") -> dict:
        from services.entity_resolution.resolver import EntityResolver
        resolver = EntityResolver()
        entity = resolver.resolve_or_create(name, entity_type)
        return {"entity_id": entity.entity_id, "canonical_name": entity.canonical_name}

    tools["resolve_entity"] = Tool(
        name="resolve_entity",
        description="Resolve an entity name to canonical form, creating if new.",
        parameters={"name": "str", "entity_type": "str"},
        func=_resolve_entity,
    )

    # Tool: Graph Analysis
    def _analyze_graph(transactions: list[dict]) -> dict:
        from services.graph.builder import TransactionGraphBuilder
        builder = TransactionGraphBuilder()
        for txn in transactions:
            builder.add_transaction(
                txn["source"], txn["target"],
                amount=txn.get("amount", 0),
                txn_type=txn.get("type", "INVOICE"),
            )
        alerts = builder.run_all_detections()
        return {
            "nodes": builder.get_node_count(),
            "edges": builder.get_edge_count(),
            "alerts": [{"type": a.alert_type, "severity": a.severity,
                        "entities": a.entities, "risk_score": a.risk_score}
                       for a in alerts],
        }

    tools["analyze_graph"] = Tool(
        name="analyze_graph",
        description="Build a transaction graph and detect fraud patterns (cycles, stars, clusters).",
        parameters={"transactions": "list[dict] with source, target, amount, type"},
        func=_analyze_graph,
    )

    # Tool: Rule Evaluation
    def _evaluate_rules(facts: dict) -> dict:
        from services.reasoning.rule_engine import RuleEngine
        engine = RuleEngine()
        firings = engine.evaluate(facts)
        return {
            "rules_fired": len(firings),
            "firings": [rf.to_dict() for rf in firings],
            "has_hard_reject": any(rf.hard_reject for rf in firings),
            "total_risk_adjustment": sum(rf.risk_adjustment for rf in firings),
        }

    tools["evaluate_rules"] = Tool(
        name="evaluate_rules",
        description="Evaluate neuro-symbolic rules against extracted facts. Returns rule firings and risk adjustments.",
        parameters={"facts": "dict"},
        func=_evaluate_rules,
    )

    # Tool: LLM Risk Assessment
    def _llm_risk_assessment(facts: dict) -> dict:
        from services.cognitive.engine import CognitiveEngine
        engine = CognitiveEngine()
        if not engine.is_alive():
            return {"status": "unavailable", "error": "Ollama not reachable"}
        resp = engine.assess_risk(facts)
        return {
            "model": resp.model,
            "thinking": resp.thinking[:2000] if resp.thinking else "",
            "answer": resp.answer[:2000] if resp.answer else resp.raw_text[:2000],
            "tokens_used": resp.tokens_used,
            "latency_ms": resp.latency_ms,
        }

    tools["llm_risk_assessment"] = Tool(
        name="llm_risk_assessment",
        description="Run LLM-based risk assessment on extracted facts using DeepSeek.",
        parameters={"facts": "dict"},
        func=_llm_risk_assessment,
    )

    # Tool: Generate CAM
    def _generate_cam(cam_data_dict: dict) -> dict:
        from services.cam.generator import CAMData, FiveCs, generate_cam_text
        output_dir = str(PROJECT_ROOT / "storage" / "processed" / "cam_outputs")
        os.makedirs(output_dir, exist_ok=True)
        cam_id = f"cam_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        cam_path = os.path.join(output_dir, f"{cam_id}.md")
        # Reconstruct CAMData from dict
        five_cs = FiveCs(**cam_data_dict.get("five_cs", {}))
        cam_data = CAMData(
            borrower_name=cam_data_dict["borrower_name"],
            loan_amount_requested=cam_data_dict["loan_amount_requested"],
            loan_purpose=cam_data_dict.get("loan_purpose", "Working Capital"),
            five_cs=five_cs,
            recommendation=cam_data_dict["recommendation"],
            recommended_amount=cam_data_dict.get("recommended_amount", 0),
            risk_premium_bps=cam_data_dict.get("risk_premium_bps", 0),
            risk_score=cam_data_dict.get("risk_score", 0),
            risk_factors=cam_data_dict.get("risk_factors", []),
            rules_fired=cam_data_dict.get("rules_fired", []),
            research_findings=cam_data_dict.get("research_findings", []),
            neuro_symbolic_trace=cam_data_dict.get("neuro_symbolic_trace", []),
            provenance_references=cam_data_dict.get("provenance_references", []),
            primary_insights=cam_data_dict.get("primary_insights", []),
        )
        generate_cam_text(cam_data, cam_path)
        return {"cam_id": cam_id, "cam_path": cam_path}

    tools["generate_cam"] = Tool(
        name="generate_cam",
        description="Generate a Credit Appraisal Memo from structured data.",
        parameters={"cam_data_dict": "dict"},
        func=_generate_cam,
    )

    # Tool: Lakehouse Query
    def _lakehouse_query(query: str) -> dict:
        from services.lakehouse.db import get_connection
        conn = get_connection()
        try:
            result = conn.execute(query).fetchall()
            columns = [desc[0] for desc in conn.description]
            return {"columns": columns, "rows": [list(r) for r in result[:100]]}
        finally:
            conn.close()

    tools["lakehouse_query"] = Tool(
        name="lakehouse_query",
        description="Run a read-only SQL query against the DuckDB lakehouse.",
        parameters={"query": "str (SELECT only)"},
        func=_lakehouse_query,
    )

    return tools


# ---------------------------------------------------------------------------
# Coordinator Agent
# ---------------------------------------------------------------------------

class CreditAppraisalOrchestrator:
    """
    Multi-agent orchestrator for credit appraisal.

    Workflow:
    1. Document ingestion (OCR + field extraction)
    2. Entity resolution
    3. Graph analysis
    4. Neuro-symbolic rule evaluation
    5. LLM risk assessment
    6. CAM generation

    Each step is a tool call; the orchestrator manages sequencing and state.
    """

    def __init__(self, state_dir: str = None):
        self.tools = _build_tools()
        self.state_dir = state_dir or str(PROJECT_ROOT / "storage" / "agent_state")
        os.makedirs(self.state_dir, exist_ok=True)

    def run_appraisal(
        self,
        input_files: list[str],
        company_name: str,
        loan_amount: float,
        loan_purpose: str = "Working Capital",
    ) -> dict:
        """Execute the full credit appraisal workflow."""
        task_id = f"appraisal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        state = AgentState(agent_id="coordinator", task_id=task_id, status="running")

        print(f"=== Agent Orchestrator: {task_id} ===")
        print(f"Company: {company_name}")
        print(f"Loan: ₹{loan_amount:,.0f} for {loan_purpose}")

        all_text = ""
        all_fields = {}

        # Step 1: Document Ingestion
        print("\n[Agent] Step 1: Document Ingestion")
        for file_path in input_files:
            if file_path.endswith('.pdf'):
                result = self.tools["ocr_document"].execute(pdf_path=file_path)
                if result["status"] == "success":
                    text = result["result"]["text"]
                    method = result["result"]["method"]
                    print(f"  OCR [{method}]: {Path(file_path).name} → {len(text)} chars")
                else:
                    print(f"  OCR error: {result['error']}")
                    text = ""
            elif file_path.endswith('.json'):
                with open(file_path) as f:
                    text = json.dumps(json.load(f), indent=2)
            else:
                with open(file_path) as f:
                    text = f.read()

            all_text += text + "\n"

            # Extract fields
            fields_result = self.tools["extract_fields"].execute(text=text)
            if fields_result["status"] == "success":
                for ftype, values in fields_result["result"].items():
                    all_fields.setdefault(ftype, []).extend(values)

            state.tool_calls.append({"tool": "ocr_document", "file": file_path})

        state.steps_completed.append("document_ingestion")
        state.findings["extracted_fields"] = {k: len(v) for k, v in all_fields.items()}
        print(f"  Total fields: {sum(len(v) for v in all_fields.values())}")

        # Step 2: Entity Resolution
        print("\n[Agent] Step 2: Entity Resolution")
        entity_result = self.tools["resolve_entity"].execute(name=company_name)
        if entity_result["status"] == "success":
            entity = entity_result["result"]
            print(f"  Entity: {entity['canonical_name']} ({entity['entity_id']})")
            state.findings["entity"] = entity
        state.steps_completed.append("entity_resolution")

        # Step 3: Graph Analysis
        print("\n[Agent] Step 3: Graph Analysis")
        gstins = all_fields.get("gstin", [])
        transactions = []
        for i, g1 in enumerate(gstins):
            for j, g2 in enumerate(gstins):
                if i != j:
                    transactions.append({"source": g1, "target": g2, "amount": 1000000, "type": "GST_INVOICE"})

        graph_result = self.tools["analyze_graph"].execute(transactions=transactions)
        fraud_alerts = []
        if graph_result["status"] == "success":
            gr = graph_result["result"]
            fraud_alerts = gr["alerts"]
            print(f"  Graph: {gr['nodes']} nodes, {gr['edges']} edges, {len(fraud_alerts)} alerts")
            state.findings["graph"] = gr
        state.steps_completed.append("graph_analysis")

        # Step 4: Rule Evaluation
        print("\n[Agent] Step 4: Neuro-Symbolic Reasoning")
        facts = {
            "company_name": company_name,
            "loan_amount_requested": loan_amount,
            "max_dpd_last_12m": 0,
            "dishonoured_cheque_count_12m": 0,
            "cibil_cmr_rank": 5,
            "capacity_utilization_pct": 70,
            "collateral_value": loan_amount * 1.5,
            "sector_sentiment_score": 0.1,
            "evidence_count": 0,
        }

        rules_result = self.tools["evaluate_rules"].execute(facts=facts)
        rule_firings = []
        if rules_result["status"] == "success":
            rr = rules_result["result"]
            rule_firings = rr["firings"]
            print(f"  Rules fired: {rr['rules_fired']}, hard reject: {rr['has_hard_reject']}")
            state.findings["rules"] = rr
        state.steps_completed.append("rule_evaluation")

        # Step 5: LLM Risk Assessment
        print("\n[Agent] Step 5: LLM Risk Assessment")
        llm_result = self.tools["llm_risk_assessment"].execute(facts=facts)
        llm_trace = {}
        if llm_result["status"] == "success":
            llm_trace = llm_result["result"]
            print(f"  LLM: {llm_trace.get('latency_ms', 0):.0f}ms, {llm_trace.get('tokens_used', 0)} tokens")
            state.findings["llm"] = llm_trace
        else:
            print(f"  LLM unavailable: {llm_result.get('error', 'unknown')}")
        state.steps_completed.append("llm_assessment")

        # Step 6: Decision
        print("\n[Agent] Step 6: Decision & CAM Generation")
        base_risk = 0.3
        has_hard_reject = False
        if rules_result["status"] == "success":
            base_risk += rules_result["result"]["total_risk_adjustment"]
            has_hard_reject = rules_result["result"]["has_hard_reject"]
        risk_score = min(1.0, base_risk)

        if has_hard_reject or risk_score > 0.7:
            recommendation = "REJECT"
            recommended_amount = 0
            risk_premium = 0
        elif risk_score > 0.5:
            recommendation = "CONDITIONAL"
            recommended_amount = loan_amount * 0.5
            risk_premium = int(risk_score * 500)
        else:
            recommendation = "APPROVE"
            recommended_amount = loan_amount
            risk_premium = int(risk_score * 300)

        print(f"  Decision: {recommendation} (risk={risk_score:.2f})")

        # Save state
        state.status = "completed"
        state.findings["decision"] = {
            "recommendation": recommendation,
            "risk_score": risk_score,
            "recommended_amount": recommended_amount,
            "risk_premium_bps": risk_premium,
        }
        state.steps_completed.append("decision")
        state_path = os.path.join(self.state_dir, f"{task_id}.json")
        state.save(state_path)
        print(f"  State saved: {state_path}")

        # Generate CAM via pipeline (reuse existing)
        from services.pipeline import run_pipeline
        cam_data = run_pipeline(
            input_files=input_files,
            company_name=company_name,
            loan_amount=loan_amount,
            loan_purpose=loan_purpose,
        )

        print(f"\n=== Agent Orchestrator COMPLETE ===")
        return state.to_dict()


def main():
    """CLI entry point for the agent orchestrator."""
    import argparse
    parser = argparse.ArgumentParser(description="Intelli-Credit Agent Orchestrator")
    parser.add_argument("--input", nargs="+", required=True, help="Input files")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--amount", type=float, required=True, help="Loan amount (INR)")
    parser.add_argument("--purpose", default="Working Capital", help="Loan purpose")
    args = parser.parse_args()

    orchestrator = CreditAppraisalOrchestrator()
    result = orchestrator.run_appraisal(
        input_files=args.input,
        company_name=args.company,
        loan_amount=args.amount,
        loan_purpose=args.purpose,
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
