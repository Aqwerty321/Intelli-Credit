"""
Presentation-grade graph intelligence for Intelli-Credit demo cases.

Builds a deterministic synthetic training corpus, trains a compact PyG graph
classifier, and scores uploaded transaction graphs with a stable output schema.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

import torch
import networkx as nx

from services.graph.builder import TransactionGraphBuilder

try:
    from torch_geometric.data import Data
    from torch_geometric.loader import DataLoader
    from torch_geometric.nn import GCNConv, global_mean_pool
    PYG_AVAILABLE = True
except Exception:  # pragma: no cover - import errors are runtime-dependent
    Data = None
    DataLoader = None
    GCNConv = None
    global_mean_pool = None
    PYG_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "storage" / "models"
MODEL_PATH = MODEL_DIR / "demo_graph_gnn.pt"
META_PATH = MODEL_DIR / "demo_graph_gnn_meta.json"

GRAPH_LABELS = [
    "clean",
    "ring",
    "star_seller",
    "dense_cluster",
    "layered_chain",
]

RINGLIKE_LABELS = {"ring", "dense_cluster", "layered_chain"}
ROLE_TO_VALUE = {
    "borrower": 1.0,
    "supplier": 0.7,
    "buyer": 0.5,
    "related_party": 0.9,
    "shell": 1.2,
    "distributor": 0.6,
    "bank": 0.2,
    "customer": 0.4,
}


def _set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)


@dataclass
class GraphInference:
    label: str
    gnn_risk_score: float
    gnn_ring_risk_score: float
    class_probabilities: dict[str, float]
    top_entities: list[dict]
    backend: str
    trained_with_pyg: bool

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "gnn_risk_score": self.gnn_risk_score,
            "gnn_ring_risk_score": self.gnn_ring_risk_score,
            "class_probabilities": self.class_probabilities,
            "top_entities": self.top_entities,
            "backend": self.backend,
            "trained_with_pyg": self.trained_with_pyg,
        }


class DemoGraphNet(torch.nn.Module):
    def __init__(self, in_channels: int, hidden_channels: int, out_channels: int):
        super().__init__()
        self.conv1 = GCNConv(in_channels, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels)
        self.head = torch.nn.Sequential(
            torch.nn.Linear(hidden_channels, hidden_channels),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_channels, out_channels),
        )

    def forward(self, x, edge_index, batch):
        x = self.conv1(x, edge_index)
        x = torch.relu(x)
        x = self.conv2(x, edge_index)
        x = torch.relu(x)
        x = global_mean_pool(x, batch)
        return self.head(x)


def _base_transaction(source: str, target: str, amount: float, day: int,
                      source_role: str, target_role: str, txn_type: str = "GST_INVOICE") -> dict:
    return {
        "source": source,
        "target": target,
        "amount": amount,
        "date": f"2025-0{1 + (day % 8)}-{1 + (day % 27):02d}",
        "type": txn_type,
        "source_role": source_role,
        "target_role": target_role,
    }


def _clean_graph(seed: int) -> list[dict]:
    rng = random.Random(seed)
    borrower = "BORROWER_A"
    suppliers = [f"SUPP_{i}" for i in range(4)]
    customers = [f"CUST_{i}" for i in range(3)]
    txns = []
    for idx, supplier in enumerate(suppliers):
        txns.append(_base_transaction(supplier, borrower, rng.randint(14, 22) * 1e5, idx, "supplier", "borrower"))
    for idx, customer in enumerate(customers, start=10):
        txns.append(_base_transaction(borrower, customer, rng.randint(11, 17) * 1e5, idx, "borrower", "customer"))
    txns.append(_base_transaction("BANK_A", borrower, 18e5, 21, "bank", "borrower", "BANK_CREDIT"))
    return txns


def _ring_graph(seed: int) -> list[dict]:
    rng = random.Random(seed)
    nodes = ["BORROWER_R", "REL_A", "REL_B", "SHELL_R"]
    roles = {
        "BORROWER_R": "borrower",
        "REL_A": "related_party",
        "REL_B": "supplier",
        "SHELL_R": "shell",
    }
    txns = []
    for idx, source in enumerate(nodes):
        target = nodes[(idx + 1) % len(nodes)]
        txns.append(_base_transaction(
            source,
            target,
            rng.randint(20, 28) * 1e5,
            idx,
            roles[source],
            roles[target],
        ))
    txns.extend([
        _base_transaction("REL_A", "BORROWER_R", 11e5, 9, "related_party", "borrower"),
        _base_transaction("SHELL_R", "REL_B", 13e5, 11, "shell", "supplier"),
    ])
    return txns


def _star_graph(seed: int) -> list[dict]:
    rng = random.Random(seed)
    hub = "STAR_SELLER"
    leaves = [f"BUYER_{i}" for i in range(6)]
    txns = []
    for idx, leaf in enumerate(leaves):
        txns.append(_base_transaction(hub, leaf, rng.randint(8, 15) * 1e5, idx, "supplier", "buyer"))
    txns.append(_base_transaction("BANK_S", hub, 12e5, 9, "bank", "supplier", "BANK_CREDIT"))
    return txns


def _dense_graph(seed: int) -> list[dict]:
    rng = random.Random(seed)
    nodes = [f"DENSE_{i}" for i in range(5)]
    txns = []
    for i, source in enumerate(nodes):
        for j, target in enumerate(nodes):
            if i == j or (i + j) % 2 == 0:
                continue
            txns.append(_base_transaction(
                source,
                target,
                rng.randint(7, 16) * 1e5,
                i + j,
                "related_party",
                "related_party",
            ))
    return txns


def _layered_graph(seed: int) -> list[dict]:
    rng = random.Random(seed)
    txns = [
        _base_transaction("BORROWER_L", "DIST_1", rng.randint(9, 14) * 1e5, 1, "borrower", "distributor"),
        _base_transaction("DIST_1", "SHELL_L1", rng.randint(9, 14) * 1e5, 2, "distributor", "shell"),
        _base_transaction("SHELL_L1", "SHELL_L2", rng.randint(9, 14) * 1e5, 3, "shell", "shell"),
        _base_transaction("SHELL_L2", "REL_L", rng.randint(9, 14) * 1e5, 4, "shell", "related_party"),
        _base_transaction("REL_L", "BORROWER_L", rng.randint(9, 14) * 1e5, 5, "related_party", "borrower"),
        _base_transaction("BANK_L", "BORROWER_L", 20e5, 7, "bank", "borrower", "BANK_CREDIT"),
    ]
    return txns


GENERATORS = {
    "clean": _clean_graph,
    "ring": _ring_graph,
    "star_seller": _star_graph,
    "dense_cluster": _dense_graph,
    "layered_chain": _layered_graph,
}


def _transactions_to_data(transactions: list[dict], label: int | None = None) -> Data:
    nodes = {}
    incoming = {}
    outgoing = {}
    incoming_value = {}
    outgoing_value = {}
    roles = {}

    for txn in transactions:
        for key, role_key in (("source", "source_role"), ("target", "target_role")):
            node = txn.get(key)
            if node not in nodes:
                nodes[node] = len(nodes)
                incoming[node] = 0
                outgoing[node] = 0
                incoming_value[node] = 0.0
                outgoing_value[node] = 0.0
                roles[node] = txn.get(role_key, "unknown")

        source = txn["source"]
        target = txn["target"]
        amount = float(txn.get("amount", 0.0))
        outgoing[source] += 1
        incoming[target] += 1
        outgoing_value[source] += amount
        incoming_value[target] += amount

    edge_pairs = []
    weights = []
    x_rows = []
    index_to_node = {idx: node for node, idx in nodes.items()}

    for txn in transactions:
        edge_pairs.append([nodes[txn["source"]], nodes[txn["target"]]])
        weights.append(float(txn.get("amount", 0.0)) / 1_000_000.0)

    for idx in range(len(nodes)):
        node = index_to_node[idx]
        in_deg = incoming[node]
        out_deg = outgoing[node]
        in_amt = incoming_value[node] / 1_000_000.0
        out_amt = outgoing_value[node] / 1_000_000.0
        net_amt = in_amt - out_amt
        total_flow = in_amt + out_amt
        role_value = ROLE_TO_VALUE.get(roles.get(node, "unknown"), 0.0)
        x_rows.append([
            float(in_deg),
            float(out_deg),
            in_amt,
            out_amt,
            net_amt,
            total_flow,
            role_value,
        ])

    data = Data(
        x=torch.tensor(x_rows, dtype=torch.float32),
        edge_index=torch.tensor(edge_pairs, dtype=torch.long).t().contiguous(),
        edge_weight=torch.tensor(weights, dtype=torch.float32),
    )
    data.node_names = [index_to_node[idx] for idx in range(len(nodes))]
    if label is not None:
        data.y = torch.tensor([label], dtype=torch.long)
    return data


def _build_training_dataset() -> list[Data]:
    dataset = []
    for class_index, class_name in enumerate(GRAPH_LABELS):
        generator = GENERATORS[class_name]
        for sample_idx in range(18):
            seed = 1200 + class_index * 100 + sample_idx
            dataset.append(_transactions_to_data(generator(seed), label=class_index))
    random.Random(7).shuffle(dataset)
    return dataset


def _train_epoch(model: DemoGraphNet, loader, optimizer, criterion) -> float:
    model.train()
    loss_total = 0.0
    for batch in loader:
        optimizer.zero_grad()
        logits = model(batch.x, batch.edge_index, batch.batch)
        loss = criterion(logits, batch.y)
        loss.backward()
        optimizer.step()
        loss_total += float(loss.item())
    return loss_total / max(1, len(loader))


def _evaluate(model: DemoGraphNet, loader) -> float:
    model.eval()
    correct = 0
    seen = 0
    with torch.no_grad():
        for batch in loader:
            logits = model(batch.x, batch.edge_index, batch.batch)
            pred = logits.argmax(dim=1)
            correct += int((pred == batch.y).sum().item())
            seen += int(batch.y.numel())
    return correct / max(1, seen)


def ensure_demo_graph_model(force_retrain: bool = False) -> dict:
    """Train the graph demo classifier if the checkpoint does not exist."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if MODEL_PATH.exists() and META_PATH.exists() and not force_retrain:
        with open(META_PATH) as f:
            return json.load(f)
    if not PYG_AVAILABLE:
        raise RuntimeError("torch_geometric is required for the demo graph model")

    _set_seed(7)
    dataset = _build_training_dataset()
    split = int(len(dataset) * 0.8)
    train_data = dataset[:split]
    test_data = dataset[split:]
    train_loader = DataLoader(train_data, batch_size=16, shuffle=True)
    test_loader = DataLoader(test_data, batch_size=16, shuffle=False)

    model = DemoGraphNet(in_channels=7, hidden_channels=24, out_channels=len(GRAPH_LABELS))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    criterion = torch.nn.CrossEntropyLoss()

    history = []
    for epoch in range(1, 31):
        loss = _train_epoch(model, train_loader, optimizer, criterion)
        if epoch % 5 == 0 or epoch == 30:
            acc = _evaluate(model, test_loader)
            history.append({"epoch": epoch, "loss": round(loss, 4), "test_accuracy": round(acc, 4)})

    torch.save({
        "state_dict": model.state_dict(),
        "graph_labels": GRAPH_LABELS,
        "trained_with_pyg": True,
    }, MODEL_PATH)
    meta = {
        "checkpoint": str(MODEL_PATH),
        "graph_labels": GRAPH_LABELS,
        "trained_with_pyg": True,
        "epochs": 30,
        "history": history,
        "feature_count": 7,
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def _load_model() -> tuple[DemoGraphNet, dict]:
    meta = ensure_demo_graph_model()
    checkpoint = torch.load(MODEL_PATH, map_location="cpu")
    model = DemoGraphNet(in_channels=7, hidden_channels=24, out_channels=len(GRAPH_LABELS))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, meta


def _builder_with_roles(transactions: list[dict]):
    builder = TransactionGraphBuilder()
    role_map = {}
    for txn in transactions:
        source = txn["source"]
        target = txn["target"]
        amount = float(txn.get("amount", 0.0))
        builder.add_transaction(
            source,
            target,
            amount=amount,
            date=txn.get("date"),
            txn_type=txn.get("type", "GST_INVOICE"),
            metadata={
                source: {"role": txn.get("source_role", "unknown")},
                target: {"role": txn.get("target_role", "unknown")},
            },
        )
        role_map[source] = txn.get("source_role", "unknown")
        role_map[target] = txn.get("target_role", "unknown")
    return builder, role_map


def _top_entities(transactions: list[dict]) -> list[dict]:
    builder, role_map = _builder_with_roles(transactions)
    metrics = builder.compute_centrality() if builder.get_edge_count() > 0 else {}
    ranked = []
    for entity, vals in metrics.items():
        score = (
            vals.get("pagerank", 0.0) * 0.45 +
            vals.get("betweenness_centrality", 0.0) * 0.35 +
            vals.get("degree_centrality", 0.0) * 0.20
        )
        ranked.append({
            "entity": entity,
            "role": role_map.get(entity, "unknown"),
            "score": round(score, 4),
            "pagerank": round(vals.get("pagerank", 0.0), 4),
        })
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:4]


def _heuristic_overlay(transactions: list[dict]) -> tuple[str, float]:
    builder, role_map = _builder_with_roles(transactions)
    if not transactions:
        return "clean", 0.0

    edge_count = max(1, len(transactions))
    node_count = max(1, builder.get_node_count())
    related_roles = {"related_party", "shell", "distributor"}
    related_edges = sum(
        1 for txn in transactions
        if txn.get("source_role") in related_roles or txn.get("target_role") in related_roles
    )
    shell_edges = sum(
        1 for txn in transactions
        if txn.get("source_role") == "shell" or txn.get("target_role") == "shell"
    )
    max_out_degree = max((builder.graph.out_degree(node) for node in builder.graph.nodes()), default=0)
    concentration = max_out_degree / max(1, node_count - 1)
    if nx.is_directed_acyclic_graph(builder.graph):
        longest_path = nx.dag_longest_path_length(builder.graph, weight=None)
    else:
        longest_path = 0

    risk = min(
        1.0,
        (related_edges / edge_count) * 0.8 +
        (shell_edges / edge_count) * 1.0 +
        concentration * 0.35 +
        max(0, longest_path - 1) * 0.08,
    )
    if shell_edges >= 2 and longest_path >= 2:
        label = "layered_chain"
    elif max_out_degree >= 4:
        label = "star_seller"
    else:
        label = "clean"
    return label, round(risk, 4)


def infer_demo_graph(transactions: list[dict]) -> GraphInference:
    """Score a transaction graph with the trained demo model."""
    if not transactions:
        return GraphInference(
            label="clean",
            gnn_risk_score=0.0,
            gnn_ring_risk_score=0.0,
            class_probabilities={label: 0.0 for label in GRAPH_LABELS},
            top_entities=[],
            backend="networkx",
            trained_with_pyg=False,
        )

    model, meta = _load_model()
    data = _transactions_to_data(transactions)
    batch = torch.zeros(data.x.shape[0], dtype=torch.long)
    with torch.no_grad():
        logits = model(data.x, data.edge_index, batch)
        probs = torch.softmax(logits, dim=1)[0]

    class_probabilities = {
        label: round(float(probs[idx]), 4)
        for idx, label in enumerate(GRAPH_LABELS)
    }
    pred_idx = int(probs.argmax().item())
    label = GRAPH_LABELS[pred_idx]
    ring_score = sum(class_probabilities[name] for name in GRAPH_LABELS if name in RINGLIKE_LABELS)
    gnn_risk_score = max(
        ring_score,
        class_probabilities.get("star_seller", 0.0) * 0.7,
    )
    heuristic_label, heuristic_risk = _heuristic_overlay(transactions)
    if label == "clean" and heuristic_label != "clean":
        label = heuristic_label
    gnn_risk_score = max(gnn_risk_score, heuristic_risk)
    return GraphInference(
        label=label,
        gnn_risk_score=round(min(1.0, gnn_risk_score), 4),
        gnn_ring_risk_score=round(min(1.0, ring_score), 4),
        class_probabilities=class_probabilities,
        top_entities=_top_entities(transactions),
        backend="networkx+pytorch_geometric" if meta.get("trained_with_pyg") else "networkx",
        trained_with_pyg=bool(meta.get("trained_with_pyg")),
    )
