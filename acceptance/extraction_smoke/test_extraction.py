"""
Acceptance Test: Extraction Accuracy
Measures per-field precision/recall on tests/extraction_smoke/ samples.
Target: > 90% on smoke set for GSTIN, PAN, invoice total, date.
Outputs JSON report to stdout.
"""
import json
import os
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_ground_truth(gt_path: Path) -> dict:
    """Load ground truth JSON for a test sample."""
    with open(gt_path) as f:
        return json.load(f)


def load_extraction(ext_path: Path) -> dict:
    """Load extraction results JSON."""
    with open(ext_path) as f:
        return json.load(f)


def normalize(value: str) -> str:
    """Normalize extracted value for comparison."""
    if value is None:
        return ""
    return re.sub(r'\s+', '', str(value).strip().upper())


def compute_field_metrics(ground_truth: list[dict], extractions: list[dict], field: str) -> dict:
    """Compute precision/recall for a specific field across all samples."""
    tp = fp = fn = 0

    for gt, ext in zip(ground_truth, extractions):
        gt_values = set(normalize(v) for v in gt.get(field, []) if v)
        ext_values = set(normalize(v) for v in ext.get(field, []) if v)

        tp += len(gt_values & ext_values)
        fp += len(ext_values - gt_values)
        fn += len(gt_values - ext_values)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "field": field,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
    }


def main():
    smoke_dir = PROJECT_ROOT / "tests" / "extraction_smoke"
    results_dir = PROJECT_ROOT / "storage" / "processed" / "extraction_results"

    fields = ["gstin", "pan", "invoice_total", "date"]
    target_threshold = 0.90

    ground_truths = []
    extractions = []

    # Collect all ground truth files
    gt_files = sorted(smoke_dir.glob("*_ground_truth.json"))

    if not gt_files:
        report = {
            "test": "extraction_accuracy",
            "status": "SKIP",
            "reason": "No ground truth files found in tests/extraction_smoke/",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(report, indent=2))
        sys.exit(0)

    for gt_file in gt_files:
        gt = load_ground_truth(gt_file)
        ground_truths.append(gt)

        # Find corresponding extraction result
        sample_id = gt_file.stem.replace("_ground_truth", "")
        ext_file = results_dir / f"{sample_id}_extracted.json"

        if ext_file.exists():
            extractions.append(load_extraction(ext_file))
        else:
            # No extraction result — all fields are false negatives
            extractions.append({field: [] for field in fields})

    # Compute metrics per field
    field_metrics = []
    all_pass = True
    for field in fields:
        metrics = compute_field_metrics(ground_truths, extractions, field)
        metrics["passes_threshold"] = metrics["f1_score"] >= target_threshold
        if not metrics["passes_threshold"]:
            all_pass = False
        field_metrics.append(metrics)

    # Aggregate
    avg_precision = sum(m["precision"] for m in field_metrics) / len(field_metrics)
    avg_recall = sum(m["recall"] for m in field_metrics) / len(field_metrics)
    avg_f1 = sum(m["f1_score"] for m in field_metrics) / len(field_metrics)

    report = {
        "test": "extraction_accuracy",
        "status": "PASS" if all_pass else "FAIL",
        "threshold": target_threshold,
        "samples_tested": len(gt_files),
        "field_metrics": field_metrics,
        "aggregate": {
            "avg_precision": round(avg_precision, 4),
            "avg_recall": round(avg_recall, 4),
            "avg_f1": round(avg_f1, 4),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(report, indent=2))
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
