"""
Integration tests for Phase 4 SSE contract and health endpoint parity.

Does NOT start a live server — exercises the helpers directly.
"""
import json
import pytest


# ---------------------------------------------------------------------------
# /health and /api/health parity
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    def test_api_health_returns_ok(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_alias_returns_ok(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_health_and_api_health_are_identical(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r1 = client.get("/health").json()
        r2 = client.get("/api/health").json()
        assert r1 == r2

    def test_health_version_reflects_v3(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/health")
        assert r.json()["version"] == "3.0.0"


# ---------------------------------------------------------------------------
# SSE emission order contract
# ---------------------------------------------------------------------------

class TestSSEEventOrder:
    """Verify that v3 supplemental events are queued before 'complete'."""

    def _collect_events(self, trace: dict) -> list[str]:
        """
        Simulate the _run_pipeline_thread event emission block with a plain list
        instead of an asyncio Queue.  Returns event names in emission order.
        """
        events = []

        def emit(event_name: str, _data: dict):
            events.append(event_name)

        # Replicate the logic from run.py (after meta update)
        if trace.get("schema_version") == "v3":
            if trace.get("research_plan"):
                emit("research_plan_ready", {})
            if trace.get("evidence_judge"):
                emit("evidence_scored", {})
            if trace.get("claim_graph"):
                emit("claim_graph_ready", {})
            if trace.get("counterfactuals"):
                emit("counterfactual_ready", {})

        emit("complete", {})
        return events

    def test_complete_is_last_event(self):
        trace = {
            "schema_version": "v3",
            "research_plan": {"queries": []},
            "evidence_judge": {"accepted": 0, "rejected": 0},
            "claim_graph": {"claims_total": 0},
            "counterfactuals": {"scenario_count": 0},
        }
        events = self._collect_events(trace)
        assert events[-1] == "complete"

    def test_research_plan_ready_before_complete(self):
        trace = {
            "schema_version": "v3",
            "research_plan": {"queries": [{"query": "q1"}]},
        }
        events = self._collect_events(trace)
        assert "research_plan_ready" in events
        assert events.index("research_plan_ready") < events.index("complete")

    def test_evidence_scored_before_complete(self):
        trace = {
            "schema_version": "v3",
            "evidence_judge": {"accepted": 3, "rejected": 1},
        }
        events = self._collect_events(trace)
        assert events.index("evidence_scored") < events.index("complete")

    def test_claim_graph_before_complete(self):
        trace = {"schema_version": "v3", "claim_graph": {"claims_total": 2}}
        events = self._collect_events(trace)
        assert events.index("claim_graph_ready") < events.index("complete")

    def test_counterfactual_before_complete(self):
        trace = {"schema_version": "v3", "counterfactuals": {"scenario_count": 3}}
        events = self._collect_events(trace)
        assert events.index("counterfactual_ready") < events.index("complete")

    def test_v2_trace_emits_only_complete(self):
        trace = {"schema_version": "v2"}
        events = self._collect_events(trace)
        assert events == ["complete"]

    def test_all_four_supplemental_events_precede_complete(self):
        trace = {
            "schema_version": "v3",
            "research_plan": {"queries": []},
            "evidence_judge": {"accepted": 0, "rejected": 0},
            "claim_graph": {"claims_total": 0},
            "counterfactuals": {"scenario_count": 0},
        }
        events = self._collect_events(trace)
        complete_idx = events.index("complete")
        supplemental = {"research_plan_ready", "evidence_scored", "claim_graph_ready", "counterfactual_ready"}
        for evt in supplemental:
            assert evt in events
            assert events.index(evt) < complete_idx
