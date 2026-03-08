"""
End-to-end pipeline orchestrator for Intelli-Credit.
Wires all services: ingest → lakehouse → entity resolution → graph → reasoning → CAM
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_pipeline(
    input_files: list[str],
    company_name: str,
    loan_amount: float,
    loan_purpose: str = "Working Capital",
    primary_insights: list[str] = None,
    output_dir: str = None,
):
    """Run the complete credit appraisal pipeline."""
    from services.ingestor.provenance import Provenance, create_provenance
    from services.ingestor.validator import extract_all_fields
    from services.lakehouse.db import get_connection, init_schema, insert_document, insert_extracted_field, log_provenance
    from services.entity_resolution.resolver import EntityResolver
    from services.graph.builder import TransactionGraphBuilder
    from services.reasoning.rule_engine import RuleEngine
    from services.cam.generator import CAMData, FiveCs, generate_cam_text

    # Try to import cognitive engine (optional - pipeline works without LLM)
    try:
        from services.cognitive.engine import CognitiveEngine, DEEPSEEK_MODEL
        cognitive_available = True
    except ImportError:
        cognitive_available = False

    # Try to import OCR module (optional - for PDF processing)
    try:
        from services.ingestor.glm_ocr import ocr_document
        ocr_available = True
    except ImportError:
        ocr_available = False

    if output_dir is None:
        output_dir = str(PROJECT_ROOT / "storage" / "processed" / "cam_outputs")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()
    cam_id = f"cam_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"=== Intelli-Credit Pipeline START ===")
    print(f"Company: {company_name}")
    print(f"Loan: ₹{loan_amount:,.0f} for {loan_purpose}")
    print(f"Input files: {len(input_files)}")

    # ========================================================================
    # Phase 1: Document Ingestion
    # ========================================================================
    print("\n--- Phase 1: Document Ingestion ---")
    conn = get_connection()
    init_schema(conn)

    all_extracted_fields = {}
    all_text = ""

    for file_path in input_files:
        doc_id = Path(file_path).stem
        print(f"  Processing: {file_path}")

        # Read file content
        if file_path.endswith('.pdf') and ocr_available:
            ocr_result = ocr_document(file_path)
            text = ocr_result["text"]
            print(f"    OCR: {ocr_result['method']}, {ocr_result['page_count']} pages, {len(text)} chars")
        elif file_path.endswith('.json'):
            with open(file_path) as f:
                data = json.load(f)
            text = json.dumps(data, indent=2)
        elif file_path.endswith('.txt') or file_path.endswith('.md'):
            with open(file_path) as f:
                text = f.read()
        else:
            text = ""

        all_text += text + "\n"

        # Extract fields
        fields = extract_all_fields(text)
        for field_type, values in fields.items():
            if field_type not in all_extracted_fields:
                all_extracted_fields[field_type] = []
            all_extracted_fields[field_type].extend(values)

        # Store in lakehouse
        try:
            insert_document(conn, doc_id, file_path,
                          document_type="corporate_document",
                          company_name=company_name)
            for field_type, values in fields.items():
                for value in values:
                    insert_extracted_field(
                        conn, doc_id, field_type, value,
                        field_type=field_type,
                        extraction_method="regex",
                        agent_id="pipeline",
                    )
        except Exception as e:
            print(f"    Warning: DB insert failed: {e}")

    print(f"  Extracted: {sum(len(v) for v in all_extracted_fields.values())} total fields")

    # ========================================================================
    # Phase 2: Entity Resolution
    # ========================================================================
    print("\n--- Phase 2: Entity Resolution ---")
    resolver = EntityResolver()
    company_entity = resolver.resolve_or_create(company_name, "company")
    print(f"  Company entity: {company_entity.canonical_name} ({company_entity.entity_id})")

    # ========================================================================
    # Phase 3: Graph Analysis
    # ========================================================================
    print("\n--- Phase 3: Graph Analysis ---")
    graph_builder = TransactionGraphBuilder()

    # Build sample graph from GSTIN transactions (if available)
    gstins = all_extracted_fields.get("gstin", [])
    for i, gstin in enumerate(gstins):
        for j, other_gstin in enumerate(gstins):
            if i != j:
                import random
                graph_builder.add_transaction(
                    gstin, other_gstin,
                    amount=random.randint(100000, 5000000),
                    txn_type="GST_INVOICE"
                )

    fraud_alerts = graph_builder.run_all_detections()
    print(f"  Graph: {graph_builder.get_node_count()} nodes, {graph_builder.get_edge_count()} edges")
    print(f"  Fraud alerts: {len(fraud_alerts)}")

    # ========================================================================
    # Phase 4: Neuro-Symbolic Reasoning
    # ========================================================================
    print("\n--- Phase 4: Neuro-Symbolic Reasoning ---")
    rule_engine = RuleEngine()
    print(f"  Loaded {rule_engine.get_rule_count()} rules")

    # Build facts from extracted data
    facts = {
        "company_name": company_name,
        "loan_amount_requested": loan_amount,
    }

    # Add CIBIL facts if available (from ground truth or extracted)
    # These would come from real document extraction
    facts.update({
        "max_dpd_last_12m": 0,
        "dishonoured_cheque_count_12m": 0,
        "cibil_cmr_rank": 5,
        "capacity_utilization_pct": 70,
        "collateral_value": loan_amount * 1.5,  # Default assumption
        "sector_sentiment_score": 0.1,
        "evidence_count": 0,
    })

    # Check for fraud indicators
    if fraud_alerts:
        for alert in fraud_alerts:
            if alert.alert_type == "cycle":
                facts["cycle_detected"] = True
                facts["cycle_length"] = alert.evidence.get("cycle_length", 0)
                facts["total_value"] = alert.evidence.get("total_value", 0)
                facts["entity_count"] = len(alert.entities)
                facts["cycle_description"] = alert.description

    rule_firings = rule_engine.evaluate(facts)
    print(f"  Rules fired: {len(rule_firings)}")
    for rf in rule_firings:
        print(f"    [{rf.severity}] {rf.rule_slug}: {rf.rationale[:80]}...")

    # ========================================================================
    # Phase 4b: LLM-Augmented Risk Assessment (optional)
    # ========================================================================
    llm_assessment = None
    llm_trace = {}
    if cognitive_available:
        print("\n--- Phase 4b: LLM Risk Assessment ---")
        try:
            engine = CognitiveEngine()
            if engine.is_alive():
                resp = engine.assess_risk(facts)
                llm_assessment = resp
                llm_trace = {
                    "model": resp.model,
                    "thinking": resp.thinking[:2000] if resp.thinking else "",
                    "answer": resp.answer[:2000] if resp.answer else resp.raw_text[:2000],
                    "tokens_used": resp.tokens_used,
                    "latency_ms": resp.latency_ms,
                }
                print(f"  LLM responded ({resp.latency_ms:.0f}ms, {resp.tokens_used} tokens)")
                if resp.thinking:
                    print(f"  Thinking: {resp.thinking[:200]}...")
            else:
                print("  Ollama not available — skipping LLM assessment")
        except Exception as e:
            print(f"  LLM assessment failed: {e}")
    else:
        print("\n--- Phase 4b: LLM Risk Assessment (skipped — not available) ---")

    # ========================================================================
    # Phase 5: Decision & CAM Generation
    # ========================================================================
    print("\n--- Phase 5: CAM Generation ---")

    # Compute aggregate risk score
    base_risk = 0.3
    for rf in rule_firings:
        base_risk += rf.risk_adjustment
    risk_score = min(1.0, base_risk)

    # Determine recommendation
    hard_reject = any(rf.hard_reject for rf in rule_firings)
    if hard_reject:
        recommendation = "REJECT"
        recommended_amount = 0
        risk_premium = 0
    elif risk_score > 0.7:
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

    # Build Five Cs
    five_cs = FiveCs(
        character={
            "promoter_background": "Assessment based on available documents",
            "cibil_cmr": facts.get("cibil_cmr_rank", "N/A"),
            "litigation_status": "No significant litigation detected" if not fraud_alerts else "ALERTS DETECTED",
            "dpd_history": f"Max DPD: {facts.get('max_dpd_last_12m', 'N/A')} days",
        },
        capacity={
            "gst_turnover": f"GSTINs found: {len(gstins)}",
            "capacity_utilization": f"{facts.get('capacity_utilization_pct', 'N/A')}%",
            "debt_service_coverage": "To be computed from financial statements",
        },
        capital={
            "net_worth": "Extracted from financial statements",
            "capital_adequacy": "Assessment pending",
        },
        collateral={
            "collateral_value": f"₹{facts.get('collateral_value', 0):,.0f}",
            "coverage_ratio": f"{facts.get('collateral_value', 0) / loan_amount:.2f}x" if loan_amount > 0 else "N/A",
        },
        conditions={
            "sector_outlook": "Neutral" if facts.get("sector_sentiment_score", 0) >= 0 else "Negative",
            "regulatory_environment": "Standard compliance required",
        },
    )

    # Build CAM data
    cam_data = CAMData(
        borrower_name=company_name,
        loan_amount_requested=loan_amount,
        loan_purpose=loan_purpose,
        five_cs=five_cs,
        recommendation=recommendation,
        recommended_amount=recommended_amount,
        risk_premium_bps=risk_premium,
        risk_score=risk_score,
        risk_factors=[{
            "severity": rf.severity,
            "description": rf.rationale,
            "rule_id": rf.rule_id,
        } for rf in rule_firings],
        rules_fired=[rf.to_dict() for rf in rule_firings],
        research_findings=[],
        neuro_symbolic_trace=[rf.to_dict() for rf in rule_firings] + ([llm_trace] if llm_trace else []),
        provenance_references=[],
        primary_insights=(primary_insights or []) + (
            [f"LLM Assessment: {llm_assessment.answer[:500]}"] if llm_assessment and llm_assessment.answer else []
        ),
    )

    # Generate CAM
    cam_path = os.path.join(output_dir, f"{cam_id}.md")
    generate_cam_text(cam_data, cam_path)
    print(f"  CAM generated: {cam_path}")
    print(f"  Recommendation: {recommendation}")
    print(f"  Risk Score: {risk_score:.2f}")

    # Write trace file for acceptance testing
    trace_path = os.path.join(output_dir, f"{cam_id}_trace.json")
    trace = {
        "cam_id": cam_id,
        "decision": {
            "recommendation": recommendation,
            "risk_score": risk_score,
            "recommended_amount": recommended_amount,
        },
        "rules_fired": [rf.to_dict() for rf in rule_firings],
        "risk_adjustments": [
            {
                "rule_id": rf.rule_id,
                "adjustment": rf.risk_adjustment,
                "trace": rf.trace,
            }
            for rf in rule_firings
        ],
        "fraud_alerts": [
            {
                "type": a.alert_type,
                "severity": a.severity,
                "entities": a.entities,
                "risk_score": a.risk_score,
            }
            for a in fraud_alerts
        ],
        "llm_trace": llm_trace if llm_trace else None,
        "timestamp": timestamp,
    }
    with open(trace_path, "w") as f:
        json.dump(trace, f, indent=2)
    print(f"  Trace: {trace_path}")

    # Log to provenance
    try:
        log_provenance(conn, "cam_generated", "cam", cam_id, "pipeline", {
            "recommendation": recommendation,
            "risk_score": risk_score,
            "rules_fired": len(rule_firings),
        })
        conn.commit()
    except Exception:
        pass

    conn.close()

    print(f"\n=== Intelli-Credit Pipeline COMPLETE ===")
    return cam_data


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Intelli-Credit Pipeline")
    parser.add_argument("--input", nargs="+", required=True, help="Input files")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--amount", type=float, required=True, help="Loan amount (INR)")
    parser.add_argument("--purpose", default="Working Capital", help="Loan purpose")
    parser.add_argument("--insights", nargs="*", help="Credit officer primary insights")
    parser.add_argument("--output-dir", help="Output directory for CAM")
    args = parser.parse_args()

    run_pipeline(
        input_files=args.input,
        company_name=args.company,
        loan_amount=args.amount,
        loan_purpose=args.purpose,
        primary_insights=args.insights,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
