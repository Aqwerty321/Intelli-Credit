#!/usr/bin/env python3
"""
Demo Intelligence Pack — manifest-driven deterministic demo sequence.

Usage:
    python scripts/demo_intelligence_pack.py prepare   # create cases, upload docs, place caches, run pipeline
    python scripts/demo_intelligence_pack.py verify    # validate verdicts, traces, v3 schema
    python scripts/demo_intelligence_pack.py cleanup   # delete demo cases
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "demo" / "intelligence_cases" / "manifest.json"
CACHE_DIR = PROJECT_ROOT / "storage" / "cache" / "research"
STATE_FILE = PROJECT_ROOT / "demo" / "intelligence_cases" / ".demo_state.json"
FORBIDDEN_PRESENTATION_TOKENS = [
    "[N/A]",
    "NaN",
    "Assessment pending",
    "To be computed",
    "Extracted from financial statements",
]

API_BASE = os.environ.get("INTELLI_API", "http://localhost:8000")
UI_BASE = os.environ.get("INTELLI_UI", "http://localhost:5173")


def _api(method: str, path: str, **kwargs):
    api_base = os.environ.get("INTELLI_API", API_BASE)
    url = f"{api_base}/api{path}"
    timeout = httpx.Timeout(300.0, connect=10.0)
    with httpx.Client(timeout=timeout) as client:
        resp = client.request(method.upper(), url, **kwargs)
    resp.raise_for_status()
    return resp


def _pick_free_port() -> int:
    return int(os.environ.get("INTELLI_EXPORT_PORT", "8010"))


def _load_manifest() -> list[dict]:
    with open(MANIFEST_PATH) as f:
        return json.load(f)["cases"]


def _sanitize(name: str) -> str:
    return re.sub(r'[^\w]', '_', name.lower())[:60]


def _generate_pdf(facts_md_path: Path, output_path: Path):
    """Generate a simple PDF from the facts.md content using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    styles = getSampleStyleSheet()
    story = []

    with open(facts_md_path) as f:
        for line in f:
            line = line.rstrip()
            if not line:
                story.append(Spacer(1, 4 * mm))
            elif line.startswith("# "):
                story.append(Paragraph(line[2:], styles["Title"]))
            elif line.startswith("## "):
                story.append(Paragraph(line[3:], styles["Heading2"]))
            elif line.startswith("- "):
                story.append(Paragraph(f"• {line[2:]}", styles["BodyText"]))
            else:
                story.append(Paragraph(line, styles["BodyText"]))

    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    doc.build(story)


def _place_research_cache(case_cfg: dict, case_dir: Path):
    """Copy the pre-shaped research cache to storage/cache/research/."""
    cache_src = case_dir / "research_cache.json"
    if not cache_src.exists():
        return
    safe_name = _sanitize(case_cfg["company_name"])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CACHE_DIR / f"{safe_name}_v3_research.json"
    shutil.copy2(cache_src, dest)
    print(f"  Placed research cache → {dest.name}")


def cmd_prepare(args):
    """Create cases, upload docs, place caches, run pipeline, add notes."""
    manifest = _load_manifest()
    total_cases = len(manifest)
    base_dir = MANIFEST_PATH.parent
    state = {"cases": {}}

    # Health check
    try:
        r = _api("get", "/health")
        print(f"API health: {r.json()}")
    except Exception as e:
        print(f"ERROR: API not reachable at {API_BASE} — {e}")
        sys.exit(1)

    for cfg in manifest:
        label = cfg["case_label"]
        folder = base_dir / cfg["folder"]
        print(f"\n{'='*60}")
        print(f"  [{label}] {cfg['company_name']}")
        print(f"{'='*60}")

        # 1. Place research cache BEFORE creating the case
        _place_research_cache(cfg, folder)

        # 2. Create case
        seed_path = base_dir / cfg["seed_payload"]
        with open(seed_path) as f:
            seed = json.load(f)
        seed.update({
            "demo_rank": cfg.get("demo_rank"),
            "demo_case_label": label,
            "presentation_summary": cfg.get("presentation_summary"),
            "graph_expectations": cfg.get("graph_expectations"),
            "expected_artifacts": cfg.get("expected_artifacts"),
        })
        r = _api("post", "/cases/", json=seed)
        case_id = r.json()["case_id"]
        print(f"  Created case: {case_id}")

        # 3. Upload documents (facts.md)
        for doc_rel in cfg["documents"]:
            doc_path = base_dir / doc_rel
            with open(doc_path, "rb") as f:
                r = _api("post", f"/cases/{case_id}/documents",
                         files={"file": (doc_path.name, f, "text/markdown")})
            print(f"  Uploaded: {doc_path.name} ({r.json()['size']} bytes)")

        # 4. Generate and upload PDF if requested
        if cfg.get("generate_pdf"):
            facts_md = base_dir / cfg["documents"][0]
            pdf_name = f"{cfg['folder']}_profile.pdf"
            pdf_path = folder / pdf_name
            _generate_pdf(facts_md, pdf_path)
            with open(pdf_path, "rb") as f:
                r = _api("post", f"/cases/{case_id}/documents",
                         files={"file": (pdf_name, f, "application/pdf")})
            print(f"  Uploaded PDF: {pdf_name} ({r.json()['size']} bytes)")

        # 5. Add officer notes if specified
        for note in cfg.get("note_steps", []):
            r = _api("post", f"/cases/{case_id}/notes", json=note)
            print(f"  Added note: {r.json()['text'][:50]}...")

        # 6. Run pipeline (sync)
        print(f"  Running pipeline...")
        r = _api("post", f"/run/{case_id}")
        result = r.json()
        print(f"  Verdict: {result['recommendation']}  risk={result['risk_score']:.2f}  "
              f"rules_fired={result['rules_fired_count']}  schema={result['schema_version']}")

        state["cases"][label] = {
            "case_id": case_id,
            "recommendation": result["recommendation"],
            "risk_score": result["risk_score"],
            "rules_fired_count": result["rules_fired_count"],
            "schema_version": result["schema_version"],
        }

    # Save state for verify/cleanup
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print("\nCase links:")
    for label, info in state["cases"].items():
        print(f"  [{label}] {UI_BASE}/cases/{info['case_id']}")
    print(f"\n{'='*60}")
    print(f"  Demo pack prepared ({total_cases} cases). State saved to {STATE_FILE.name}")
    print(f"{'='*60}")


def cmd_verify(args):
    """Validate verdicts, traces, and v3 schema against manifest expectations."""
    if not STATE_FILE.exists():
        print("ERROR: No .demo_state.json — run 'prepare' first.")
        sys.exit(1)

    with open(STATE_FILE) as f:
        state = json.load(f)

    manifest = _load_manifest()
    total_cases = len(manifest)
    errors = []

    for cfg in manifest:
        label = cfg["case_label"]
        expected = cfg["expected"]
        folder = MANIFEST_PATH.parent / cfg["folder"]
        actual = state["cases"].get(label)
        if not actual:
            errors.append(f"[{label}] Missing from state")
            continue

        case_id = actual["case_id"]
        print(f"\n  [{label}] Verifying {case_id}...")

        # Check recommendation
        if actual["recommendation"] != expected["recommendation"]:
            errors.append(f"[{label}] recommendation: {actual['recommendation']} != {expected['recommendation']}")

        # Check risk_score bounds
        rs = actual["risk_score"]
        if rs < expected["risk_score_min"] or rs > expected["risk_score_max"]:
            errors.append(f"[{label}] risk_score {rs:.2f} outside [{expected['risk_score_min']}, {expected['risk_score_max']}]")

        # Check schema_version
        if actual["schema_version"] != expected["schema_version"]:
            errors.append(f"[{label}] schema_version: {actual['schema_version']} != {expected['schema_version']}")

        # Full case detail from API
        r = _api("get", f"/cases/{case_id}")
        detail = r.json()
        graph_trace = detail.get("trace", {}).get("graph_trace", {})

        # Check trace exists
        if "trace" not in detail:
            errors.append(f"[{label}] trace missing from case detail")
        else:
            trace = detail["trace"]

            # Check rules fired
            rule_slugs = [rf.get("slug") or rf.get("rule_slug", "") for rf in trace.get("rule_firings", [])]
            for expected_slug in expected.get("rules_fired", []):
                if expected_slug not in rule_slugs:
                    errors.append(f"[{label}] expected rule '{expected_slug}' not fired. Fired: {rule_slugs}")

            # Check hard_reject flag
            if expected.get("hard_reject"):
                has_hard = any(rf.get("hard_reject") for rf in trace.get("rule_firings", []))
                if not has_hard:
                    errors.append(f"[{label}] expected hard_reject but none found")

            # v3 trace keys
            for key in ("schema_version", "research_plan", "evidence_judge", "claim_graph", "counterfactuals"):
                if key not in trace:
                    errors.append(f"[{label}] trace missing v3 key: {key}")

        # Check CAM
        try:
            _api("get", f"/cases/{case_id}/cam")
        except Exception:
            errors.append(f"[{label}] CAM not generated")

        # Check officer notes count
        notes = detail.get("officer_notes", [])
        expected_note_count = len(cfg.get("note_steps", []))
        if len(notes) != expected_note_count:
            errors.append(f"[{label}] notes count: {len(notes)} != {expected_note_count}")

        # Coverage assertions from manifest
        assertions = cfg.get("coverage_assertions", [])
        if "no_rules_fired" in assertions and detail.get("trace", {}).get("rules_fired_count", 0) != 0:
            errors.append(f"[{label}] expected no rules fired")
        if "exactly_3_rules_fired" in assertions and detail.get("trace", {}).get("rules_fired_count", 0) != 3:
            errors.append(f"[{label}] expected exactly 3 rules fired")
        if "officer_notes_count_2" in assertions and len(notes) != 2:
            errors.append(f"[{label}] expected exactly 2 officer notes")
        if "officer_notes_count_2" in assertions:
            notes_in_trace = detail.get("trace", {}).get("orchestration_impact", {}).get("officer_notes_count")
            if notes_in_trace != 2:
                errors.append(f"[{label}] trace officer_notes_count {notes_in_trace} != 2")
        if "hard_reject_triggered" in assertions:
            has_hard = any(rf.get("hard_reject") for rf in detail.get("trace", {}).get("rule_firings", []))
            if not has_hard:
                errors.append(f"[{label}] expected hard_reject trigger")
        if "cycle_detected_in_graph" in assertions:
            graph = detail.get("trace", {}).get("graph_trace", {})
            has_cycle = graph.get("suspicious_cycles", 0) > 0 or bool(graph.get("fraud_alerts", []))
            if not has_cycle:
                errors.append(f"[{label}] expected cycle/fraud graph evidence")
        if "research_cache_used" in assertions:
            cache_src = folder / "research_cache.json"
            research = detail.get("research", {})
            if not cache_src.exists():
                errors.append(f"[{label}] research cache source file missing")
            else:
                with open(cache_src) as f:
                    cache_data = json.load(f)
                if research.get("research_timestamp") != cache_data.get("research_timestamp"):
                    errors.append(f"[{label}] research cache timestamp mismatch (cache likely not used)")
        if "graph_stats_present" in assertions:
            if graph_trace.get("edge_count", 0) <= 0:
                errors.append(f"[{label}] expected graph_trace.edge_count > 0")
            if graph_trace.get("node_count", 0) <= 0:
                errors.append(f"[{label}] expected graph_trace.node_count > 0")
            if not graph_trace.get("graph_backend"):
                errors.append(f"[{label}] graph_backend missing")
            if graph_trace.get("gnn_risk_score") is None:
                errors.append(f"[{label}] gnn_risk_score missing")
            graph_expected = cfg.get("graph_expectations", {})
            if graph_expected:
                if graph_trace.get("node_count") != graph_expected.get("node_count"):
                    errors.append(f"[{label}] node_count {graph_trace.get('node_count')} != {graph_expected.get('node_count')}")
                if graph_trace.get("edge_count") != graph_expected.get("edge_count"):
                    errors.append(f"[{label}] edge_count {graph_trace.get('edge_count')} != {graph_expected.get('edge_count')}")
                if graph_trace.get("suspicious_cycles") != graph_expected.get("suspicious_cycles"):
                    errors.append(f"[{label}] suspicious_cycles {graph_trace.get('suspicious_cycles')} != {graph_expected.get('suspicious_cycles')}")
                gnn_score = float(graph_trace.get("gnn_risk_score", 0.0))
                if gnn_score < graph_expected.get("gnn_risk_score_min", 0.0) or gnn_score > graph_expected.get("gnn_risk_score_max", 1.0):
                    errors.append(
                        f"[{label}] gnn_risk_score {gnn_score:.2f} outside [{graph_expected.get('gnn_risk_score_min')}, {graph_expected.get('gnn_risk_score_max')}]"
                    )
        if "presentation_safe" in assertions:
            payload = json.dumps(detail, ensure_ascii=True)
            for token in FORBIDDEN_PRESENTATION_TOKENS:
                if token in payload:
                    errors.append(f"[{label}] forbidden token present: {token}")

        if not errors or not any(label in e for e in errors):
            print(f"    ✓ All checks passed")

    print(f"\n{'='*60}")
    if errors:
        print(f"  VERIFY FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"    ✗ {e}")
        sys.exit(1)
    else:
        print(f"  ✓ All {total_cases} cases verified successfully.")
    print(f"{'='*60}")


def cmd_cleanup(args):
    """Delete demo cases and remove caches."""
    if not STATE_FILE.exists():
        print("No .demo_state.json found — nothing to clean up.")
        return

    with open(STATE_FILE) as f:
        state = json.load(f)

    for label, info in state.get("cases", {}).items():
        case_id = info["case_id"]
        try:
            _api("delete", f"/cases/{case_id}")
            print(f"  [{label}] Deleted {case_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print(f"  [{label}] Already deleted: {case_id}")
            else:
                print(f"  [{label}] Delete failed: {e}")

    # Remove pre-placed research caches
    manifest = _load_manifest()
    for cfg in manifest:
        safe_name = _sanitize(cfg["company_name"])
        cache_file = CACHE_DIR / f"{safe_name}_v3_research.json"
        if cache_file.exists():
            cache_file.unlink()
            print(f"  Removed cache: {cache_file.name}")

    # Remove generated PDFs
    base_dir = MANIFEST_PATH.parent
    for cfg in manifest:
        folder = base_dir / cfg["folder"]
        generated_pdf = folder / f"{cfg['folder']}_profile.pdf"
        if generated_pdf.exists():
            generated_pdf.unlink()
            print(f"  Removed generated PDF: {generated_pdf.name}")

    STATE_FILE.unlink(missing_ok=True)
    print("  Cleanup complete.")


def cmd_export(args):
    """Build the frontend, serve the app, capture screenshots, and write an asset index."""
    if not STATE_FILE.exists():
        print("ERROR: No .demo_state.json - run 'prepare' first.")
        sys.exit(1)

    frontend_dir = PROJECT_ROOT / "frontend"
    assets_dir = PROJECT_ROOT / "demo" / "assets"
    screenshot_dir = PROJECT_ROOT / "demo" / "assets" / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    export_port = int(os.environ.get("INTELLI_EXPORT_PORT", _pick_free_port()))
    export_base = f"http://127.0.0.1:{export_port}"
    server_log = assets_dir / "export_server.log"

    print("  Building frontend...")
    subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True)

    env = os.environ.copy()
    env["INTELLI_API"] = export_base
    env["PLAYWRIGHT_BASE_URL"] = export_base
    env["SCREENSHOT_OUTDIR"] = str(screenshot_dir)

    print(f"  Starting FastAPI server for screenshot capture on :{export_port}...")
    log_handle = open(server_log, "w")
    server = subprocess.Popen(
        [
            str(PROJECT_ROOT / ".venv" / "bin" / "python"),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(export_port),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )

    try:
        for _ in range(30):
            try:
                httpx.get(f"{export_base}/api/health", timeout=3.0).raise_for_status()
                break
            except Exception:
                if server.poll() is not None:
                    break
                time.sleep(1)
        else:
            pass

        if server.poll() is not None:
            raise RuntimeError(
                f"FastAPI server exited before becoming healthy. See {server_log}"
            )

        try:
            httpx.get(f"{export_base}/api/health", timeout=3.0).raise_for_status()
        except Exception as exc:
            raise RuntimeError(
                f"FastAPI server did not become healthy on :{export_port}. See {server_log}"
            ) from exc

        print("  Capturing screenshots...")
        subprocess.run(
            ["npx", "playwright", "test", "e2e/demo_pack_capture.spec.js", "--project=chromium"],
            cwd=frontend_dir,
            check=True,
            env=env,
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        log_handle.close()

    with open(STATE_FILE) as f:
        state = json.load(f)
    asset_index = PROJECT_ROOT / "demo" / "assets" / "asset_index.md"
    lines = [
        "# Demo Asset Index",
        "",
        "## Screenshots",
        f"- Case list: `{screenshot_dir / '01_case_list.png'}`",
    ]
    for label in sorted(state.get("cases", {}).keys()):
        lines.append(f"- {label} detail: `{screenshot_dir / (label.lower() + '_detail.png')}`")
        lines.append(f"- {label} graph: `{screenshot_dir / (label.lower() + '_graph.png')}`")
    asset_index.write_text("\n".join(lines) + "\n")
    print(f"  Asset index written: {asset_index}")


def main():
    parser = argparse.ArgumentParser(description="Demo Intelligence Pack orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare", help="Create cases, upload docs, run pipeline")
    sub.add_parser("verify", help="Validate verdicts against manifest")
    sub.add_parser("cleanup", help="Delete demo cases and caches")
    sub.add_parser("export", help="Capture presentation-ready screenshots and asset index")

    args = parser.parse_args()
    {"prepare": cmd_prepare, "verify": cmd_verify, "cleanup": cmd_cleanup, "export": cmd_export}[args.command](args)


if __name__ == "__main__":
    main()
