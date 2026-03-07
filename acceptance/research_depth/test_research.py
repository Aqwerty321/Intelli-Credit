"""
Acceptance Test: Research Depth
Verifies that research agents surface ≥1 corroborated external evidence
item not present in the initial research files for each test company.
Outputs JSON report to stdout.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def main():
    research_dir = PROJECT_ROOT / "tests" / "research_depth"
    results_dir = PROJECT_ROOT / "storage" / "processed" / "research_results"

    # Load test company profiles
    company_files = sorted(research_dir.glob("*.json"))
    if not company_files:
        report = {
            "test": "research_depth",
            "status": "SKIP",
            "reason": "No company profiles found in tests/research_depth/",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(report, indent=2))
        sys.exit(0)

    company_results = []
    all_pass = True

    for cf in company_files:
        with open(cf) as f:
            company = json.load(f)

        company_name = company.get("name", cf.stem)
        initial_facts = set(company.get("known_facts", []))

        # Load research results for this company
        result_file = results_dir / f"{cf.stem}_research.json"
        if result_file.exists():
            with open(result_file) as f:
                research = json.load(f)
            findings = research.get("findings", [])
        else:
            findings = []

        # Count external evidence not in initial facts
        novel_findings = []
        for finding in findings:
            fact_text = finding.get("summary", "")
            # Check if this fact is genuinely new (not in initial dataset)
            is_novel = not any(
                known.lower() in fact_text.lower() for known in initial_facts
            )
            if is_novel and finding.get("corroborated", False):
                novel_findings.append({
                    "summary": fact_text,
                    "source": finding.get("source", "unknown"),
                    "confidence": finding.get("confidence", 0.0),
                })

        passes = len(novel_findings) >= 1
        if not passes:
            all_pass = False

        company_results.append({
            "company": company_name,
            "total_findings": len(findings),
            "novel_corroborated_findings": len(novel_findings),
            "top_findings": novel_findings[:10],  # hits@10
            "passes_threshold": passes,
        })

    report = {
        "test": "research_depth",
        "status": "PASS" if all_pass else "FAIL",
        "min_corroborated_hits": 1,
        "companies_tested": len(company_files),
        "companies_passing": sum(1 for r in company_results if r["passes_threshold"]),
        "results": company_results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(report, indent=2))
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
