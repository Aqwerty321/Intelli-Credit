"""
Unit tests for Phase 4 scorecard schema acceptance (v2 and v3).
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.generate_scorecard import score_case


# ---------------------------------------------------------------------------
# Minimal helpers
# ---------------------------------------------------------------------------

def _make_trace(schema_version: str, extra_keys: dict = None) -> dict:
    base = {
        "schema_version": schema_version,
        "rule_firings": [],
        "rules_fired_count": 0,
        "decision": {"recommendation": "APPROVE", "risk_score": 0.3},
        "graph_trace": {"edges_examined": 0, "suspicious_cycles": 0, "fraud_alerts": []},
        "timestamp": "2026-03-08T00:00:00Z",
        "minimum_risk_policy": [],
    }
    if extra_keys:
        base.update(extra_keys)
    return base


def _make_case(schema_version: str, extra_trace_keys: dict = None) -> dict:
    """Wrap trace/meta/research into the shape score_case() expects."""
    return {
        "meta": {
            "company_name": "Sunrise Textiles Ltd",  # maps to APPROVE in EXPECTED_VERDICTS
            "case_id": "test-001",
            "recommendation": "APPROVE",
            "risk_score": 0.3,
        },
        "trace": _make_trace(schema_version, extra_trace_keys),
        "research": {"findings": []},
    }


# ---------------------------------------------------------------------------
# Schema compliance scoring tests
# ---------------------------------------------------------------------------

class TestScorecardSchemaV2:
    def test_v2_trace_gets_schema_points(self):
        result = score_case(_make_case("v2"))
        assert result["scores"]["schema"] > 0

    def test_v2_trace_schema_note_includes_v2(self):
        result = score_case(_make_case("v2"))
        assert "v2" in result["notes"]["schema"]


class TestScorecardSchemaV3:
    def test_v3_trace_scores_at_least_as_well_as_v2(self):
        r_v2 = score_case(_make_case("v2"))
        r_v3 = score_case(_make_case("v3", {
            "v2_compat": True,
            "research_plan": {"queries": []},
            "claim_graph": {"claims_total": 0},
            "counterfactuals": {"scenario_count": 0},
            "evidence_judge": {"accepted": 0, "rejected": 0},
        }))
        assert r_v3["scores"]["schema"] >= r_v2["scores"]["schema"]

    def test_v3_trace_with_all_new_fields_earns_bonus(self):
        result = score_case(_make_case("v3", {
            "research_plan": {"queries": [{"query": "q"}]},
            "claim_graph": {"claims_total": 1},
            "counterfactuals": {"scenario_count": 2},
            "evidence_judge": {"accepted": 1, "rejected": 0},
        }))
        # max schema score is 15
        assert result["scores"]["schema"] == 15

    def test_v3_trace_without_new_fields_scores_same_as_v2(self):
        r_v2 = score_case(_make_case("v2"))
        r_v3 = score_case(_make_case("v3"))  # no v3-specific fields
        assert r_v2["scores"]["schema"] == r_v3["scores"]["schema"]

    def test_unknown_schema_version_gets_zero_bonus(self):
        result = score_case(_make_case("v99"))
        notes = result["notes"]["schema"]
        assert "✗" in notes or "v99" in notes

    def test_schema_note_includes_version_string(self):
        result = score_case(_make_case("v3"))
        assert "v3" in result["notes"]["schema"]


# ---------------------------------------------------------------------------
# Orchestration context propagation
# ---------------------------------------------------------------------------

class TestOrchestrationContextPropagation:
    """Assert sector/location/officer_notes appear in pipeline signature."""

    def test_pipeline_accepts_sector_kwarg(self):
        import inspect
        from services.pipeline import run_pipeline
        sig = inspect.signature(run_pipeline)
        assert "sector" in sig.parameters

    def test_pipeline_accepts_location_kwarg(self):
        import inspect
        from services.pipeline import run_pipeline
        sig = inspect.signature(run_pipeline)
        assert "location" in sig.parameters

    def test_pipeline_accepts_promoters_kwarg(self):
        import inspect
        from services.pipeline import run_pipeline
        sig = inspect.signature(run_pipeline)
        assert "promoters" in sig.parameters

    def test_pipeline_accepts_officer_notes_kwarg(self):
        import inspect
        from services.pipeline import run_pipeline
        sig = inspect.signature(run_pipeline)
        assert "officer_notes" in sig.parameters

    def test_officer_notes_appear_in_orchestration_impact(self):
        """officer_notes_count in trace matches what was injected."""
        import json
        import tempfile
        import os
        from services.pipeline import run_pipeline

        doc = "CIBIL CMR Rank: 4\nMax DPD (last 12M): 0\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_path = os.path.join(tmpdir, "test.txt")
            with open(doc_path, "w") as f:
                f.write(doc)

            notes = [{"author": "officer1", "text": "Promoter background clean.", "note_type": "observation"}]
            run_pipeline(
                input_files=[doc_path],
                company_name="Test Co for Notes",
                loan_amount=500_000,
                output_dir=tmpdir,
                officer_notes=notes,
            )

            import glob
            trace_files = glob.glob(os.path.join(tmpdir, "*_trace.json"))
            assert trace_files
            with open(trace_files[-1]) as f:
                trace = json.load(f)

            impact = trace.get("orchestration_impact", {})
            assert impact.get("officer_notes_count") == 1
