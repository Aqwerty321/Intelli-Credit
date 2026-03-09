from services.graph.intelligence import ensure_demo_graph_model, infer_demo_graph


def _ring_transactions():
    return [
        {"source": "Borrower", "target": "RelatedA", "amount": 3_800_000, "source_role": "borrower", "target_role": "related_party"},
        {"source": "RelatedA", "target": "ShellA", "amount": 3_600_000, "source_role": "related_party", "target_role": "shell"},
        {"source": "ShellA", "target": "ShellB", "amount": 3_400_000, "source_role": "shell", "target_role": "shell"},
        {"source": "ShellB", "target": "Borrower", "amount": 4_200_000, "source_role": "shell", "target_role": "borrower"},
        {"source": "Borrower", "target": "Broker", "amount": 2_100_000, "source_role": "borrower", "target_role": "related_party"},
        {"source": "Broker", "target": "ShellA", "amount": 2_050_000, "source_role": "related_party", "target_role": "shell"},
    ]


def _clean_transactions():
    return [
        {"source": "Bank", "target": "Borrower", "amount": 5_200_000, "source_role": "bank", "target_role": "borrower"},
        {"source": "SupplierA", "target": "Borrower", "amount": 2_100_000, "source_role": "supplier", "target_role": "borrower"},
        {"source": "SupplierB", "target": "Borrower", "amount": 1_900_000, "source_role": "supplier", "target_role": "borrower"},
        {"source": "Borrower", "target": "CustomerA", "amount": 2_400_000, "source_role": "borrower", "target_role": "customer"},
        {"source": "Borrower", "target": "CustomerB", "amount": 2_200_000, "source_role": "borrower", "target_role": "customer"},
    ]


def test_demo_graph_model_trains_and_scores_ring_higher_than_clean():
    meta = ensure_demo_graph_model(force_retrain=True)
    assert meta["trained_with_pyg"] is True

    ring = infer_demo_graph(_ring_transactions())
    clean = infer_demo_graph(_clean_transactions())

    assert ring.backend == "networkx+pytorch_geometric"
    assert ring.gnn_risk_score > clean.gnn_risk_score
    assert ring.gnn_risk_score > 0.5
    assert len(ring.top_entities) > 0
