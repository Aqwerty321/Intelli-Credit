"""
Acceptance Test: Explainability Coverage
Verifies that all hard rejects have deterministic PyReason/LNN traces (100%)
and >90% of risk adjustments have traces.
Outputs JSON report to stdout.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def main():
    cam_dir = PROJECT_ROOT / "storage" / "processed" / "cam_outputs"

    if not cam_dir.exists():
        report = {
            "test": "explainability_coverage",
            "status": "SKIP",
            "reason": "No CAM outputs found in storage/processed/cam_outputs/",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(report, indent=2))
        sys.exit(0)

    trace_files = sorted(cam_dir.glob("*_trace.json"))
    if not trace_files:
        report = {
            "test": "explainability_coverage",
            "status": "SKIP",
            "reason": "No trace files found in CAM outputs",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(report, indent=2))
        sys.exit(0)

    hard_rejects_total = 0
    hard_rejects_with_trace = 0
    risk_adjustments_total = 0
    risk_adjustments_with_trace = 0

    cam_results = []

    for tf in trace_files:
        with open(tf) as f:
            trace = json.load(f)

        cam_id = tf.stem.replace("_trace", "")
        decision = trace.get("decision", {})
        rules_fired = trace.get("rules_fired", [])

        is_reject = decision.get("recommendation") == "REJECT"
        has_trace = len(rules_fired) > 0

        if is_reject:
            hard_rejects_total += 1
            if has_trace:
                hard_rejects_with_trace += 1

        # Count risk adjustments
        adjustments = trace.get("risk_adjustments", [])
        for adj in adjustments:
            risk_adjustments_total += 1
            if adj.get("trace"):
                risk_adjustments_with_trace += 1

        cam_results.append({
            "cam_id": cam_id,
            "decision": decision.get("recommendation", "UNKNOWN"),
            "rules_fired": len(rules_fired),
            "has_complete_trace": has_trace,
            "risk_adjustments": len(adjustments),
            "adjustments_with_trace": sum(1 for a in adjustments if a.get("trace")),
        })

    # Compute coverage
    reject_coverage = (
        hard_rejects_with_trace / hard_rejects_total
        if hard_rejects_total > 0 else 1.0
    )
    adjustment_coverage = (
        risk_adjustments_with_trace / risk_adjustments_total
        if risk_adjustments_total > 0 else 1.0
    )

    reject_pass = reject_coverage >= 1.0
    adjustment_pass = adjustment_coverage >= 0.90
    all_pass = reject_pass and adjustment_pass

    report = {
        "test": "explainability_coverage",
        "status": "PASS" if all_pass else "FAIL",
        "hard_reject_coverage": {
            "total": hard_rejects_total,
            "with_trace": hard_rejects_with_trace,
            "coverage": round(reject_coverage, 4),
            "target": 1.0,
            "passes": reject_pass,
        },
        "risk_adjustment_coverage": {
            "total": risk_adjustments_total,
            "with_trace": risk_adjustments_with_trace,
            "coverage": round(adjustment_coverage, 4),
            "target": 0.90,
            "passes": adjustment_pass,
        },
        "cam_details": cam_results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(report, indent=2))
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
