"""Tests for the graph topology and features API endpoints."""
import json
import os
import shutil
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CASES_DIR = PROJECT_ROOT / "storage" / "cases"


@pytest.fixture
def case_with_graph():
    """Create a case with a trace containing graph topology."""
    # Create case
    resp = client.post("/api/cases/", json={
        "company_name": "GraphTestCo",
        "loan_amount": 5000000,
        "loan_purpose": "Working Capital",
    })
    assert resp.status_code == 201
    case_id = resp.json()["case_id"]

    # Write a trace file with graph_topology and graph_transactions
    trace = {
        "schema_version": "v3",
        "decision": {"recommendation": "CONDITIONAL", "risk_score": 0.45},
        "graph_trace": {
            "edge_count": 3,
            "node_count": 3,
            "suspicious_cycles": 1,
            "fraud_alerts": [
                {"type": "cycle", "severity": "CRITICAL", "entities": ["A", "B", "C"], "risk_score": 0.8}
            ],
            "gnn_label": "ring",
            "gnn_risk_score": 0.72,
            "class_probabilities": {"clean": 0.1, "ring": 0.6, "star_seller": 0.1, "dense_cluster": 0.1, "layered_chain": 0.1},
            "top_entities": [{"entity": "A", "role": "borrower", "score": 0.9, "pagerank": 0.33}],
            "visual_ready": True,
            "graph_topology": {
                "nodes": [
                    {"id": "A", "role": "borrower", "in_degree": 1, "out_degree": 1, "pagerank": 0.333, "betweenness": 0.5, "hub_score": 0.4, "authority_score": 0.4},
                    {"id": "B", "role": "supplier", "in_degree": 1, "out_degree": 1, "pagerank": 0.333, "betweenness": 0.5, "hub_score": 0.3, "authority_score": 0.3},
                    {"id": "C", "role": "buyer", "in_degree": 1, "out_degree": 1, "pagerank": 0.333, "betweenness": 0.5, "hub_score": 0.3, "authority_score": 0.3},
                ],
                "edges": [
                    {"source": "A", "target": "B", "weight": 1000000, "count": 1, "transactions": []},
                    {"source": "B", "target": "C", "weight": 500000, "count": 1, "transactions": []},
                    {"source": "C", "target": "A", "weight": 800000, "count": 1, "transactions": []},
                ],
            },
            "graph_transactions": [
                {"transaction_id": "A_B_0", "source": "A", "target": "B", "amount": 1000000, "type": "GST_INVOICE", "source_role": "borrower", "target_role": "supplier"},
                {"transaction_id": "B_C_0", "source": "B", "target": "C", "amount": 500000, "type": "GST_INVOICE", "source_role": "supplier", "target_role": "buyer"},
                {"transaction_id": "C_A_0", "source": "C", "target": "A", "amount": 800000, "type": "GST_INVOICE", "source_role": "buyer", "target_role": "borrower"},
            ],
        },
    }
    trace_path = CASES_DIR / case_id / "run_test_trace.json"
    with open(trace_path, "w") as f:
        json.dump(trace, f)

    yield case_id

    # Cleanup
    shutil.rmtree(CASES_DIR / case_id, ignore_errors=True)


@pytest.fixture
def case_without_trace():
    """Create a case with no trace at all."""
    resp = client.post("/api/cases/", json={
        "company_name": "NoTraceTestCo",
        "loan_amount": 1000000,
    })
    case_id = resp.json()["case_id"]
    yield case_id
    shutil.rmtree(CASES_DIR / case_id, ignore_errors=True)


class TestGraphTopologyEndpoint:
    """Tests for GET /api/cases/{case_id}/graph"""

    def test_returns_full_topology(self, case_with_graph):
        resp = client.get(f"/api/cases/{case_with_graph}/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["case_id"] == case_with_graph
        assert data["node_count"] == 3
        assert data["edge_count"] == 3
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 3
        assert data["gnn_label"] == "ring"
        assert data["gnn_risk_score"] == 0.72
        assert data["visual_ready"] is True

    def test_nodes_have_centrality_metrics(self, case_with_graph):
        resp = client.get(f"/api/cases/{case_with_graph}/graph")
        node = resp.json()["nodes"][0]
        assert "id" in node
        assert "role" in node
        assert "pagerank" in node
        assert "betweenness" in node
        assert "hub_score" in node

    def test_edges_have_weight(self, case_with_graph):
        resp = client.get(f"/api/cases/{case_with_graph}/graph")
        edge = resp.json()["edges"][0]
        assert "source" in edge
        assert "target" in edge
        assert "weight" in edge

    def test_includes_fraud_alerts(self, case_with_graph):
        resp = client.get(f"/api/cases/{case_with_graph}/graph")
        alerts = resp.json()["fraud_alerts"]
        assert len(alerts) == 1
        assert alerts[0]["type"] == "cycle"

    def test_includes_class_probabilities(self, case_with_graph):
        resp = client.get(f"/api/cases/{case_with_graph}/graph")
        probs = resp.json()["class_probabilities"]
        assert "ring" in probs
        assert probs["ring"] == 0.6

    def test_404_no_trace(self, case_without_trace):
        resp = client.get(f"/api/cases/{case_without_trace}/graph")
        assert resp.status_code == 404

    def test_404_bad_case(self):
        resp = client.get("/api/cases/nonexistent_case/graph")
        assert resp.status_code == 404


class TestGraphFeaturesEndpoint:
    """Tests for GET /api/cases/{case_id}/graph/features"""

    def test_returns_feature_vectors(self, case_with_graph):
        resp = client.get(f"/api/cases/{case_with_graph}/graph/features")
        assert resp.status_code == 200
        data = resp.json()
        assert data["case_id"] == case_with_graph
        assert data["node_count"] == 3
        assert data["feature_dim"] == 7
        assert len(data["node_names"]) == 3
        assert len(data["features"]) == 3
        # Each feature vector has 7 dimensions
        for fv in data["features"]:
            assert len(fv) == 7

    def test_edge_index_structure(self, case_with_graph):
        resp = client.get(f"/api/cases/{case_with_graph}/graph/features")
        data = resp.json()
        edge_index = data["edge_index"]
        assert len(edge_index) == 2  # [sources, targets]
        assert len(edge_index[0]) == len(edge_index[1])  # same length
        assert len(edge_index[0]) == 3  # 3 edges

    def test_includes_role_to_value(self, case_with_graph):
        resp = client.get(f"/api/cases/{case_with_graph}/graph/features")
        roles = resp.json()["role_to_value"]
        assert "borrower" in roles
        assert roles["borrower"] == 1.0

    def test_empty_when_no_transactions(self, case_without_trace):
        # Even though case exists, it has no trace
        resp = client.get(f"/api/cases/{case_without_trace}/graph/features")
        assert resp.status_code == 404

    def test_404_bad_case(self):
        resp = client.get("/api/cases/nonexistent_case/graph/features")
        assert resp.status_code == 404
