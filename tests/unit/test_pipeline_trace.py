"""
Unit tests for pipeline trace contract (Workstream A).
Validates: envelope keys, rules_fired_count accuracy, minimum_risk_policy,
graph_trace structure, and trace schema_version.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="module")
def trace_from_pipeline():
    """Run the pipeline with a minimal known-fact document and return the trace."""
    from services.pipeline import run_pipeline

    # Create a temporary fact document that will trigger at least CMR rule
    fact_doc = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False,
        prefix="test_pipeline_trace_"
    )
    fact_doc.write(
        "Credit Assessment Document\n"
        "Company: Test Pipeline Co\n"
        "CIBIL CMR Rank: 9\n"
        "Max DPD Last 12 Months: 120\n"
        "Collateral Value: INR 5000000\n"
    )
    fact_doc.close()

    with tempfile.TemporaryDirectory() as out_dir:
        run_pipeline(
            input_files=[fact_doc.name],
            company_name="Test Pipeline Co",
            loan_amount=10_000_000,
            loan_purpose="Working Capital",
            research_findings=[],
            output_dir=out_dir,
        )
        trace_files = sorted(Path(out_dir).glob("*_trace.json"))
        assert trace_files, "No trace file was written"
        with open(trace_files[-1]) as f:
            trace = json.load(f)

    os.unlink(fact_doc.name)
    return trace


class TestTraceEnvelopeKeys:
    def test_schema_version_present(self, trace_from_pipeline):
        assert "schema_version" in trace_from_pipeline
        assert trace_from_pipeline["schema_version"] == "v2"

    def test_rule_firings_key_is_list(self, trace_from_pipeline):
        """Key must be rule_firings (not rules_fired) to match frontend contract."""
        assert "rule_firings" in trace_from_pipeline, (
            "trace must have 'rule_firings' key — if 'rules_fired' is present instead, "
            "the frontend contract is broken"
        )
        assert isinstance(trace_from_pipeline["rule_firings"], list)

    def test_rules_fired_count_matches_list(self, trace_from_pipeline):
        assert "rules_fired_count" in trace_from_pipeline
        assert trace_from_pipeline["rules_fired_count"] == len(trace_from_pipeline["rule_firings"])

    def test_decision_subkeys(self, trace_from_pipeline):
        dec = trace_from_pipeline["decision"]
        assert "recommendation" in dec
        assert "risk_score" in dec
        assert "recommended_amount" in dec

    def test_graph_trace_present(self, trace_from_pipeline):
        assert "graph_trace" in trace_from_pipeline
        gt = trace_from_pipeline["graph_trace"]
        assert "edges_examined" in gt
        assert "suspicious_cycles" in gt
        assert "no_graph_evidence" in gt
        assert "fraud_alerts" in gt

    def test_timestamp_present(self, trace_from_pipeline):
        assert "timestamp" in trace_from_pipeline


class TestMinimumRiskPolicy:
    def test_minimum_risk_policy_present(self, trace_from_pipeline):
        assert "minimum_risk_policy" in trace_from_pipeline
        assert isinstance(trace_from_pipeline["minimum_risk_policy"], list)

    def test_defaults_applied_when_facts_missing(self, trace_from_pipeline):
        """When uploaded doc lacks most facts, minimum_risk_policy must be non-empty."""
        # The test doc only has CMR + DPD, so collateral/capacity etc use defaults
        policy = trace_from_pipeline["minimum_risk_policy"]
        assert len(policy) > 0, "Expected at least some defaults to be applied"

    def test_policy_entries_have_required_keys(self, trace_from_pipeline):
        for entry in trace_from_pipeline["minimum_risk_policy"]:
            assert "field" in entry
            assert "default_value" in entry
            assert "reason" in entry


class TestRuleFiringSchema:
    def test_firing_has_schema_version_v2(self, trace_from_pipeline):
        firings = trace_from_pipeline["rule_firings"]
        if not firings:
            pytest.skip("No rules fired in this test run")
        for rf in firings:
            assert rf.get("schema_version") == "v2"

    def test_firing_has_missing_data_flags(self, trace_from_pipeline):
        firings = trace_from_pipeline["rule_firings"]
        if not firings:
            pytest.skip("No rules fired in this test run")
        for rf in firings:
            assert "missing_data_flags" in rf
            assert isinstance(rf["missing_data_flags"], list)

    def test_no_old_rules_fired_key(self, trace_from_pipeline):
        """The old 'rules_fired' key (list) must not exist at trace top level."""
        # rules_fired_count (int) is allowed; rules_fired (list) is not
        if "rules_fired" in trace_from_pipeline:
            assert isinstance(trace_from_pipeline["rules_fired"], int) or \
                   not isinstance(trace_from_pipeline["rules_fired"], list), \
                   "Found old 'rules_fired' list key — rename to 'rule_firings'"
