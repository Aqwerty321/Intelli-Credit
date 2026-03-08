"""
Integration tests for v3 trace contract.

Verifies that run_pipeline produces a valid v3 trace with all new fields,
and that v2_compat: True preserves backward-compatible v2 field names.
"""
import json
import os
import tempfile
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def v3_trace(tmp_path_factory):
    """Run pipeline on a minimal test document and return the trace dict."""
    tmpdir = str(tmp_path_factory.mktemp("trace_v3"))

    # Write a rich test document with CMR, DPD, collateral, capacity
    doc = tmpdir + "/test_cibil.txt"
    with open(doc, "w") as f:
        f.write("""
CIBIL Commercial Report
Company: Omega Castings Pvt Ltd

CMR Rank: 8/10
Max DPD (Last 12 Months): 45 days
Dishonoured Cheques: 2
Risk Category: High Risk

Collateral Value: INR 50000000
Capacity Utilization: 65%
GST Declared Turnover: INR 1,00,00,000
Bank Statement Credits (12M): INR 90,00,000

ITC Available (GSTR-2A): Rs. 500000
ITC Claimed (GSTR-3B): Rs. 650000

Criminal Cases: 0
Civil Cases: 1
""")

    from services.pipeline import run_pipeline
    cam = run_pipeline(
        input_files=[doc],
        company_name="Omega Castings",
        loan_amount=25_000_000,
        output_dir=tmpdir,
    )

    trace_files = sorted(Path(tmpdir).glob("*_trace.json"))
    assert trace_files, "No trace file generated"
    with open(trace_files[-1]) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# v3 schema contract tests
# ---------------------------------------------------------------------------

class TestV3SchemaContract:
    def test_schema_version_is_v3(self, v3_trace):
        assert v3_trace["schema_version"] == "v3"

    def test_v2_compat_flag(self, v3_trace):
        assert v3_trace["v2_compat"] is True

    def test_all_v2_fields_preserved(self, v3_trace):
        for field in ("cam_id", "decision", "rule_firings", "rules_fired_count",
                      "risk_adjustments", "minimum_risk_policy", "graph_trace", "timestamp"):
            assert field in v3_trace, f"v2 field '{field}' missing from v3 trace"

    def test_decision_has_required_keys(self, v3_trace):
        decision = v3_trace["decision"]
        for key in ("recommendation", "risk_score", "recommended_amount"):
            assert key in decision

    def test_rule_firings_list(self, v3_trace):
        assert isinstance(v3_trace["rule_firings"], list)

    def test_minimum_risk_policy_list(self, v3_trace):
        assert isinstance(v3_trace["minimum_risk_policy"], list)

    def test_graph_trace_structure(self, v3_trace):
        gt = v3_trace["graph_trace"]
        for key in ("edges_examined", "suspicious_cycles", "fraud_alerts", "no_graph_evidence"):
            assert key in gt


# ---------------------------------------------------------------------------
# v3 new-field tests
# ---------------------------------------------------------------------------

class TestV3NewFields:
    def test_research_plan_present(self, v3_trace):
        # research_plan may be None if ResearchRouterAgent is unavailable, but key must exist
        assert "research_plan" in v3_trace

    def test_claim_graph_present(self, v3_trace):
        assert "claim_graph" in v3_trace

    def test_counterfactuals_present(self, v3_trace):
        assert "counterfactuals" in v3_trace

    def test_evidence_judge_present(self, v3_trace):
        assert "evidence_judge" in v3_trace

    def test_orchestration_mode_present(self, v3_trace):
        assert v3_trace.get("orchestration_mode") in ("llm", "deterministic")

    def test_fallbacks_used_is_list(self, v3_trace):
        assert isinstance(v3_trace.get("fallbacks_used", []), list)

    def test_claim_graph_structure(self, v3_trace):
        cg = v3_trace.get("claim_graph")
        if cg is None:
            pytest.skip("ClaimGraph agent unavailable")
        for key in ("claims_total", "corroborated", "contradictions", "claims"):
            assert key in cg

    def test_counterfactuals_structure(self, v3_trace):
        cf = v3_trace.get("counterfactuals")
        if cf is None:
            pytest.skip("CounterfactualChallenger produced no result")
        assert "original_recommendation" in cf
        assert "scenarios" in cf
        assert isinstance(cf["scenarios"], list)

    def test_evidence_judge_structure(self, v3_trace):
        ej = v3_trace.get("evidence_judge", {})
        for key in ("accepted", "rejected", "fallback"):
            assert key in ej


# ---------------------------------------------------------------------------
# Domain facts extraction tests (via trace context)
# ---------------------------------------------------------------------------

class TestV3DomainFactExtraction:
    """Verify that the v3 extractor actually picks up facts from the rich doc."""

    def test_cmr_extracted_from_rank_slash_10(self, v3_trace):
        """CMR Rank: 8/10 should be parsed and produce a HIGH/CRITICAL rule firing."""
        firings = v3_trace["rule_firings"]
        # cibil_cmr_risk rule should have fired given CMR=8
        cmr_firings = [r for r in firings if "cmr" in r.get("rule_slug", "").lower() or
                       "cibil" in r.get("rule_slug", "").lower()]
        assert cmr_firings, "No CMR rule fired despite CMR=8 in document"

    def test_dpd_rule_fired(self, v3_trace):
        """Max DPD 45 days should fire a DPD rule (threshold usually at 30+)."""
        firings = v3_trace["rule_firings"]
        dpd_firings = [r for r in firings if "dpd" in r.get("rule_slug", "").lower()]
        assert dpd_firings, "No DPD rule fired despite max DPD=45 in document"

    def test_no_spurious_cycle_detection(self, v3_trace):
        """Document has no circular trading language; graph should have no edges."""
        gt = v3_trace["graph_trace"]
        assert gt["edges_examined"] == 0
        assert gt["no_graph_evidence"] is True
