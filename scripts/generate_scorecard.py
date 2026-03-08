#!/usr/bin/env python3
"""
generate_scorecard.py — Judge Scorecard Generator for Intelli-Credit
=====================================================================
Reads all completed case outputs from storage/cases/ and produces:
  - reports/judge_scorecard.md  (human-readable Markdown)
  - reports/judge_scorecard.json  (machine-readable for automation)

Evaluates each case against hackathon criteria:
  1. Correctness        — recommendation matches domain-expected outcome
  2. Explainability     — trace has rule_firings, rationale, minimum_risk_policy
  3. Evidence Quality   — research findings with source_tier + corroboration
  4. Schema Compliance  — schema_version == "v2", required trace keys present
  5. Risk Calibration   — risk_score in the expected band for each verdict

Usage:
  python scripts/generate_scorecard.py [--cases-dir storage/cases]
                                       [--out-dir reports]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ─── Criteria weights ────────────────────────────────────────────────────────
CRITERIA = {
    "correctness":     {"label": "Correctness",      "max": 30, "weight": 0.30},
    "explainability":  {"label": "Explainability",   "max": 25, "weight": 0.25},
    "evidence":        {"label": "Evidence Quality", "max": 20, "weight": 0.20},
    "schema":          {"label": "Schema Compliance","max": 15, "weight": 0.15},
    "calibration":     {"label": "Risk Calibration", "max": 10, "weight": 0.10},
}

# Expected verdict → risk_score band
EXPECTED_BANDS = {
    "APPROVE":      (0.00, 0.40),
    "CONDITIONAL":  (0.35, 0.70),
    "REJECT":       (0.65, 1.00),
}

# Expected verdicts for known seed companies (case-insensitive match on company_name fragment)
EXPECTED_VERDICTS = {
    "sunrise textiles":            "APPROVE",
    "apex steel":                  "CONDITIONAL",
    "greenfield pharma":           "REJECT",
}


def load_case(case_dir: Path) -> dict | None:
    """Load a case's meta + latest trace from case_dir."""
    meta_path = case_dir / "meta.json"
    if not meta_path.exists():
        return None

    with open(meta_path) as f:
        meta = json.load(f)

    if meta.get("status") != "complete":
        return None  # Skip incomplete cases

    trace_files = sorted(case_dir.glob("*_trace.json"))
    trace = {}
    if trace_files:
        with open(trace_files[-1]) as f:
            trace = json.load(f)

    research_file = next(case_dir.glob("*_research.json"), None)
    research = {}
    if research_file:
        with open(research_file) as f:
            research = json.load(f)

    return {"meta": meta, "trace": trace, "research": research, "dir": str(case_dir)}


def score_case(case: dict) -> dict:
    """Score a single case across all criteria. Returns scoring dict."""
    meta = case["meta"]
    trace = case["trace"]
    research = case["research"]

    company_name = meta.get("company_name", "")
    actual_verdict = meta.get("recommendation", "")
    risk_score = meta.get("risk_score") or trace.get("decision", {}).get("risk_score", 0.0)

    scores = {}
    notes = {}

    # ── 1. Correctness ──────────────────────────────────────────────────────
    expected_verdict = None
    for fragment, verdict in EXPECTED_VERDICTS.items():
        if fragment.lower() in company_name.lower():
            expected_verdict = verdict
            break

    if expected_verdict is None:
        # Unknown case — can't score correctness automatically
        scores["correctness"] = 15
        notes["correctness"] = f"Unknown company — no expected verdict configured. Got: {actual_verdict}"
    elif actual_verdict == expected_verdict:
        scores["correctness"] = 30
        notes["correctness"] = f"✓ {actual_verdict} matches expected {expected_verdict}"
    else:
        scores["correctness"] = 0
        notes["correctness"] = f"✗ Got {actual_verdict}, expected {expected_verdict}"

    # ── 2. Explainability ───────────────────────────────────────────────────
    rule_firings = trace.get("rule_firings", [])
    has_firings = len(rule_firings) > 0
    has_rationale = all("rationale" in rf or "rationale_rendered" in rf for rf in rule_firings) if rule_firings else False
    has_mrp = bool(trace.get("minimum_risk_policy"))
    has_graph_trace = "graph_trace" in trace
    has_inputs = any("inputs" in rf for rf in rule_firings)

    expl_score = 0
    expl_score += 10 if has_firings else 0
    expl_score += 5 if has_rationale else 0
    expl_score += 5 if has_mrp else 0
    expl_score += 5 if has_graph_trace else 0
    scores["explainability"] = min(expl_score, 25)
    notes["explainability"] = (
        f"rule_firings={len(rule_firings)}, rationale={'✓' if has_rationale else '✗'}, "
        f"min_risk_policy={'✓' if has_mrp else '✗'}, graph_trace={'✓' if has_graph_trace else '✗'}"
    )

    # ── 3. Evidence Quality ─────────────────────────────────────────────────
    findings = research.get("findings", [])
    corroborated = sum(1 for f in findings if (f.get("corroboration_count") or 0) >= 2)
    authoritative = sum(1 for f in findings if f.get("source_tier") in ("authoritative", "credible"))
    low_tier = sum(1 for f in findings if f.get("source_tier") == "low")
    corroborated_ratio = corroborated / len(findings) if findings else 0

    ev_score = 0
    ev_score += 5 if len(findings) > 0 else 0
    ev_score += 8 if corroborated_ratio >= 0.5 else (4 if corroborated_ratio >= 0.25 else 0)
    ev_score += 7 if authoritative > 0 else 0
    ev_score -= 3 if low_tier > len(findings) / 2 else 0
    scores["evidence"] = max(0, min(ev_score, 20))
    notes["evidence"] = (
        f"findings={len(findings)}, corroborated={corroborated}, "
        f"authoritative/credible={authoritative}, low_tier={low_tier}"
    )

    # ── 4. Schema Compliance ────────────────────────────────────────────────
    required_keys = ("schema_version", "rule_firings", "rules_fired_count", "decision", "graph_trace", "timestamp")
    present = [k for k in required_keys if k in trace]
    schema_version = trace.get("schema_version", "")
    schema_ok = schema_version in ("v2", "v3")
    schema_is_v3 = schema_version == "v3"
    count_match = trace.get("rules_fired_count") == len(trace.get("rule_firings", []))
    # v3 bonus: reward traces with new agent fields
    v3_bonus_keys = ("research_plan", "claim_graph", "counterfactuals", "evidence_judge")
    v3_present = sum(1 for k in v3_bonus_keys if trace.get(k) is not None)

    sch_score = 0
    sch_score += len(present) * 2  # up to 12 points
    sch_score += 3 if schema_ok else 0
    sch_score += min(v3_present, 4) if schema_is_v3 else 0  # up to +4 bonus for v3 fields
    scores["schema"] = min(sch_score, 15)
    notes["schema"] = (
        f"present_keys={len(present)}/{len(required_keys)}, "
        f"schema={'✓' if schema_ok else '✗'}({schema_version}), "
        f"v3_fields={v3_present}/4, count_match={'✓' if count_match else '✗'}"
    )

    # ── 5. Risk Calibration ─────────────────────────────────────────────────
    band = EXPECTED_BANDS.get(expected_verdict or actual_verdict)
    if band and risk_score is not None:
        lo, hi = band
        in_band = lo <= risk_score <= hi
        scores["calibration"] = 10 if in_band else 3
        notes["calibration"] = (
            f"risk_score={risk_score:.3f}, band=[{lo},{hi}], {'✓ in band' if in_band else '✗ out of band'}"
        )
    else:
        scores["calibration"] = 5
        notes["calibration"] = f"risk_score={risk_score} (band unknown)"

    # ── Total ────────────────────────────────────────────────────────────────
    total = sum(scores.values())
    max_total = sum(c["max"] for c in CRITERIA.values())
    pct = round(total / max_total * 100, 1)

    return {
        "company_name": company_name,
        "case_id": meta.get("case_id", ""),
        "actual_verdict": actual_verdict,
        "expected_verdict": expected_verdict,
        "risk_score": risk_score,
        "rules_fired_count": trace.get("rules_fired_count", 0),
        "scores": scores,
        "notes": notes,
        "total": total,
        "max_total": max_total,
        "pct": pct,
    }


def render_markdown(scored_cases: list[dict], generated_at: str) -> str:
    lines = [
        "# Intelli-Credit — Judge Scorecard",
        "",
        f"> Generated: {generated_at}  ",
        f"> Cases evaluated: {len(scored_cases)}",
        "",
        "---",
        "",
        "## Scoring Criteria",
        "",
        "| Criterion | Max | Weight |",
        "| --------- | --- | ------ |",
    ]
    for key, c in CRITERIA.items():
        lines.append(f"| {c['label']} | {c['max']} | {int(c['weight']*100)}% |")

    lines += ["", "---", "", "## Case Results", ""]

    for sc in scored_cases:
        verdict_icon = "✅" if sc["actual_verdict"] == sc["expected_verdict"] else "❌"
        lines += [
            f"### {sc['company_name']}",
            "",
            f"- **Case ID:** `{sc['case_id']}`",
            f"- **Expected:** {sc['expected_verdict'] or '(unknown)'}  "
            f"**Actual:** {sc['actual_verdict']}  {verdict_icon}",
            f"- **Risk Score:** {sc['risk_score']:.3f}" if sc['risk_score'] is not None else "- **Risk Score:** N/A",
            f"- **Rules Fired:** {sc['rules_fired_count']}",
            "",
            "| Criterion | Score | Max | Notes |",
            "| --------- | ----- | --- | ----- |",
        ]
        for key, c in CRITERIA.items():
            s = sc["scores"].get(key, 0)
            m = c["max"]
            n = sc["notes"].get(key, "")
            lines.append(f"| {c['label']} | {s} | {m} | {n} |")

        lines += [
            "",
            f"**Total: {sc['total']} / {sc['max_total']} ({sc['pct']}%)**",
            "",
            "---",
            "",
        ]

    # Summary table
    lines += [
        "## Summary",
        "",
        "| Company | Verdict | Expected | Score | % |",
        "| ------- | ------- | -------- | ----- | - |",
    ]
    for sc in scored_cases:
        match = "✅" if sc["actual_verdict"] == sc["expected_verdict"] else "❌"
        lines.append(
            f"| {sc['company_name']} | {sc['actual_verdict']} "
            f"| {sc['expected_verdict'] or '?'} {match} "
            f"| {sc['total']}/{sc['max_total']} | {sc['pct']}% |"
        )

    overall_avg = round(sum(sc["pct"] for sc in scored_cases) / len(scored_cases), 1) if scored_cases else 0
    correct = sum(1 for sc in scored_cases if sc["actual_verdict"] == sc["expected_verdict"])
    lines += [
        "",
        f"**Correctness: {correct}/{len(scored_cases)}**  ",
        f"**Average Score: {overall_avg}%**",
        "",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate judge scorecard for Intelli-Credit cases")
    parser.add_argument("--cases-dir", default="storage/cases", help="Path to cases storage dir")
    parser.add_argument("--out-dir", default="reports", help="Output directory for scorecard files")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    cases_dir = repo_root / args.cases_dir
    out_dir = repo_root / args.out_dir

    if not cases_dir.exists():
        print(f"ERROR: cases dir not found: {cases_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {cases_dir} for completed cases...")
    scored_cases = []
    for case_subdir in sorted(cases_dir.iterdir()):
        if not case_subdir.is_dir():
            continue
        case = load_case(case_subdir)
        if case is None:
            continue
        scored = score_case(case)
        scored_cases.append(scored)
        print(f"  [{scored['actual_verdict']:11s}] {scored['company_name']:40s} {scored['total']}/{scored['max_total']} ({scored['pct']}%)")

    if not scored_cases:
        print("No completed cases found. Run the pipeline first.")
        sys.exit(0)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Write Markdown
    md_path = out_dir / "judge_scorecard.md"
    with open(md_path, "w") as f:
        f.write(render_markdown(scored_cases, generated_at))
    print(f"\n  Markdown: {md_path}")

    # Write JSON
    json_path = out_dir / "judge_scorecard.json"
    with open(json_path, "w") as f:
        json.dump({
            "generated_at": generated_at,
            "cases": scored_cases,
            "summary": {
                "total_cases": len(scored_cases),
                "correct": sum(1 for sc in scored_cases if sc["actual_verdict"] == sc["expected_verdict"]),
                "average_pct": round(sum(sc["pct"] for sc in scored_cases) / len(scored_cases), 1),
            }
        }, f, indent=2)
    print(f"  JSON:     {json_path}")

    correct = sum(1 for sc in scored_cases if sc["actual_verdict"] == sc["expected_verdict"])
    avg = round(sum(sc["pct"] for sc in scored_cases) / len(scored_cases), 1)
    print(f"\n  Correctness: {correct}/{len(scored_cases)} | Average: {avg}%")


if __name__ == "__main__":
    main()
