"""
Phase 6 — Demo Intelligence Pack integration tests.

Manifest-driven: creates each case, uploads parser-friendly documents
(+ generated PDF where configured), runs the pipeline, and asserts verdicts
+ v3 trace + coverage assertions.

Run:  pytest tests/integration/test_demo_cases.py -v --tb=short
"""
import json
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = PROJECT_ROOT / "demo" / "intelligence_cases" / "manifest.json"
CACHE_DIR = PROJECT_ROOT / "storage" / "cache" / "research"
FORBIDDEN_PRESENTATION_TOKENS = [
    "[N/A]",
    "NaN",
    "Assessment pending",
    "To be computed",
    "Extracted from financial statements",
]


def _sanitize(name: str) -> str:
    return re.sub(r'[^\w]', '_', name.lower())[:60]


def _generate_pdf(facts_md_path: Path, output_path: Path):
    """Generate a simple PDF from markdown lines for mixed-modality ingestion tests."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

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
                story.append(Paragraph(f"* {line[2:]}", styles["BodyText"]))
            else:
                story.append(Paragraph(line, styles["BodyText"]))

    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    doc.build(story)


def _assert_manifest_coverage(cfg: dict, detail: dict):
    """Enforce manifest-declared coverage assertions for a single case."""
    label = cfg["case_label"]
    trace = detail.get("trace", {})
    assertions = cfg.get("coverage_assertions", [])
    notes = detail.get("officer_notes", [])

    if "trace_exists" in assertions:
        assert "trace" in detail, f"[{label}] trace missing"

    if "cam_generated" in assertions:
        assert bool(trace.get("cam_id")), f"[{label}] expected cam_id in trace"

    if "no_rules_fired" in assertions:
        assert trace.get("rules_fired_count", 0) == 0, f"[{label}] expected no rules fired"

    if "exactly_3_rules_fired" in assertions:
        assert trace.get("rules_fired_count", 0) == 3, f"[{label}] expected exactly 3 rules fired"

    if "officer_notes_count_2" in assertions:
        assert len(notes) == 2, f"[{label}] expected exactly 2 notes"
        assert trace.get("orchestration_impact", {}).get("officer_notes_count") == 2, (
            f"[{label}] trace officer_notes_count mismatch"
        )

    if "hard_reject_triggered" in assertions:
        has_hard = any(rf.get("hard_reject") for rf in trace.get("rule_firings", []))
        assert has_hard, f"[{label}] expected hard_reject trigger"

    if "cycle_detected_in_graph" in assertions:
        graph = trace.get("graph_trace", {})
        has_cycle = graph.get("suspicious_cycles", 0) > 0 or bool(graph.get("fraud_alerts", []))
        assert has_cycle, f"[{label}] expected cycle/fraud graph evidence"

    if "research_cache_used" in assertions:
        cache_src = MANIFEST_PATH.parent / cfg["folder"] / "research_cache.json"
        if cache_src.exists():
            with open(cache_src) as f:
                cache_data = json.load(f)
            research = detail.get("research", {})
            assert research.get("research_timestamp") == cache_data.get("research_timestamp"), (
                f"[{label}] research cache timestamp mismatch"
            )

    if "graph_stats_present" in assertions:
        graph = trace.get("graph_trace", {})
        assert graph.get("edge_count", 0) > 0, f"[{label}] expected graph edge_count > 0"
        assert graph.get("node_count", 0) > 0, f"[{label}] expected graph node_count > 0"
        assert graph.get("graph_backend"), f"[{label}] expected graph backend"
        assert graph.get("gnn_risk_score") is not None, f"[{label}] expected gnn_risk_score"

    if "presentation_safe" in assertions:
        payload = json.dumps(detail, ensure_ascii=True)
        for token in FORBIDDEN_PRESENTATION_TOKENS:
            assert token not in payload, f"[{label}] forbidden token present: {token}"


@pytest.fixture(scope="module")
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def manifest():
    with open(MANIFEST_PATH) as f:
        return json.load(f)["cases"]


@pytest.fixture(scope="module")
def run_cases(client, manifest):
    """Run each manifest case once and cache results for all tests in module."""
    base_dir = MANIFEST_PATH.parent
    generated_pdfs: list[Path] = []
    created_cases: list[str] = []
    results: dict[str, dict] = {}

    for cfg in manifest:
        label = cfg["case_label"]
        folder = base_dir / cfg["folder"]

        # Place research cache
        cache_src = folder / "research_cache.json"
        if cache_src.exists():
            safe_name = _sanitize(cfg["company_name"])
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            dest = CACHE_DIR / f"{safe_name}_v3_research.json"
            shutil.copy2(cache_src, dest)

        # Create case
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
        r = client.post("/api/cases/", json=seed)
        assert r.status_code == 201, f"[{label}] create failed: {r.text}"
        case_id = r.json()["case_id"]
        created_cases.append(case_id)

        # Upload markdown docs
        for doc_rel in cfg["documents"]:
            doc_path = base_dir / doc_rel
            with open(doc_path, "rb") as f:
                r = client.post(
                    f"/api/cases/{case_id}/documents",
                    files={"file": (doc_path.name, f, "text/markdown")},
                )
            assert r.status_code == 200, f"[{label}] md upload failed: {r.text}"

        # Upload generated PDF when enabled
        pdf_name = None
        if cfg.get("generate_pdf"):
            facts_md = base_dir / cfg["documents"][0]
            pdf_name = f"test_{cfg['folder']}_profile.pdf"
            pdf_path = folder / pdf_name
            _generate_pdf(facts_md, pdf_path)
            generated_pdfs.append(pdf_path)
            with open(pdf_path, "rb") as f:
                r = client.post(
                    f"/api/cases/{case_id}/documents",
                    files={"file": (pdf_name, f, "application/pdf")},
                )
            assert r.status_code == 200, f"[{label}] pdf upload failed: {r.text}"

        # Add notes before run (so orchestration_impact captures them)
        for note in cfg.get("note_steps", []):
            r = client.post(f"/api/cases/{case_id}/notes", json=note)
            assert r.status_code == 201, f"[{label}] note add failed: {r.text}"

        # Run pipeline sync
        r = client.post(f"/api/run/{case_id}")
        assert r.status_code == 200, f"[{label}] run failed: {r.text}"
        result = r.json()

        # Fetch case detail
        r = client.get(f"/api/cases/{case_id}")
        assert r.status_code == 200, f"[{label}] detail fetch failed: {r.text}"
        detail = r.json()

        results[label] = {
            "cfg": cfg,
            "case_id": case_id,
            "result": result,
            "detail": detail,
            "pdf_name": pdf_name,
        }

    yield results

    # Cleanup created cases
    for case_id in created_cases:
        client.delete(f"/api/cases/{case_id}")

    # Cleanup caches
    for cfg in manifest:
        safe = _sanitize(cfg["company_name"])
        cache_file = CACHE_DIR / f"{safe}_v3_research.json"
        if cache_file.exists():
            cache_file.unlink()

    # Cleanup generated PDFs
    for pdf in generated_pdfs:
        if pdf.exists():
            pdf.unlink()


class TestDemoPack:
    def test_manifest_cases_executed(self, manifest, run_cases):
        assert len(run_cases) == len(manifest)
        for cfg in manifest:
            assert cfg["case_label"] in run_cases

    def test_recommendation_and_schema(self, run_cases):
        for label, data in run_cases.items():
            cfg = data["cfg"]
            result = data["result"]
            expected = cfg["expected"]
            assert result["recommendation"] == expected["recommendation"], f"[{label}] bad recommendation"
            assert result["schema_version"] == expected["schema_version"], f"[{label}] bad schema version"

    def test_risk_score_bounds(self, run_cases):
        for label, data in run_cases.items():
            cfg = data["cfg"]
            result = data["result"]
            expected = cfg["expected"]
            assert expected["risk_score_min"] <= result["risk_score"] <= expected["risk_score_max"], (
                f"[{label}] risk score out of range"
            )

    def test_expected_rules_fired(self, run_cases):
        for label, data in run_cases.items():
            cfg = data["cfg"]
            trace = data["detail"].get("trace", {})
            rule_slugs = [rf.get("slug") or rf.get("rule_slug", "") for rf in trace.get("rule_firings", [])]
            for expected_slug in cfg["expected"].get("rules_fired", []):
                assert expected_slug in rule_slugs, f"[{label}] expected rule '{expected_slug}' not fired"

    def test_v3_trace_keys_present(self, run_cases):
        for label, data in run_cases.items():
            trace = data["detail"].get("trace", {})
            for key in ("schema_version", "research_plan", "evidence_judge", "claim_graph", "counterfactuals"):
                assert key in trace, f"[{label}] missing v3 key: {key}"

    def test_graph_trace_enriched(self, run_cases):
        for label, data in run_cases.items():
            trace = data["detail"].get("trace", {})
            graph = trace.get("graph_trace", {})
            for key in ("node_count", "edge_count", "graph_backend", "gnn_risk_score", "gnn_label", "top_entities", "evidence_source", "visual_ready"):
                assert key in graph, f"[{label}] missing graph_trace key: {key}"

    def test_no_presentation_placeholders(self, run_cases):
        for label, data in run_cases.items():
            payload = json.dumps(data["detail"], ensure_ascii=True)
            for token in FORBIDDEN_PRESENTATION_TOKENS:
                assert token not in payload, f"[{label}] forbidden token present: {token}"

    def test_pdf_uploaded_when_enabled(self, run_cases):
        for label, data in run_cases.items():
            cfg = data["cfg"]
            if not cfg.get("generate_pdf"):
                continue
            docs = data["detail"].get("documents", [])
            assert data["pdf_name"] in docs, f"[{label}] generated PDF not present in documents"

    def test_cam_download_available(self, run_cases, client):
        for label, data in run_cases.items():
            case_id = data["case_id"]
            r = client.get(f"/api/cases/{case_id}/cam")
            assert r.status_code == 200, f"[{label}] CAM not downloadable"

    def test_manifest_coverage_assertions(self, run_cases):
        for _label, data in run_cases.items():
            _assert_manifest_coverage(data["cfg"], data["detail"])
