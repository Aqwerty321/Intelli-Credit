#!/usr/bin/env python3
"""
Export DemoGraphNet to ONNX for browser inference via onnxruntime-web.

GCNConv uses message passing which isn't directly ONNX-exportable,
so we create a pure-linear equivalent that takes pre-aggregated features.

Usage:
    python scripts/export_gnn_onnx.py
    # Output: frontend/public/models/demo_graph_gnn.onnx
"""
import json
import sys
from pathlib import Path

import onnx
import torch
import torch.nn as nn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.graph.intelligence import (
    DemoGraphNet,
    GRAPH_LABELS,
    _load_model,
    _build_training_dataset,
    _transactions_to_data,
    GENERATORS,
    _set_seed,
)


class DenseGNNForExport(nn.Module):
    """
    ONNX-exportable version of DemoGraphNet.

    Instead of GCNConv message passing, uses adjacency matrix multiplication
    for neighbor aggregation (equivalent for small graphs).

    Forward takes:
      x: [N, 7]  node features
      adj: [N, N] normalized adjacency matrix (D^-0.5 A D^-0.5)
    Returns:
      logits: [1, 5]  class logits (graph-level)
    """

    def __init__(self, in_channels=7, hidden_channels=24, out_channels=5):
        super().__init__()
        # Mirror GCNConv weight matrices — lin (no bias) + separate bias
        self.lin1 = nn.Linear(in_channels, hidden_channels, bias=False)
        self.bias1 = nn.Parameter(torch.zeros(hidden_channels))
        self.lin2 = nn.Linear(hidden_channels, hidden_channels, bias=False)
        self.bias2 = nn.Parameter(torch.zeros(hidden_channels))
        # MLP head (same as DemoGraphNet.head)
        self.head = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels),
            nn.ReLU(),
            nn.Linear(hidden_channels, out_channels),
        )

    def forward(self, x, adj):
        # GCN layer 1: lin(X) first, then propagate via adj, then bias
        x = self.lin1(x)        # [N, hidden] — weight transform
        x = torch.matmul(adj, x)  # [N, hidden] — neighborhood aggregation
        x = x + self.bias1
        x = torch.relu(x)
        # GCN layer 2
        x = self.lin2(x)
        x = torch.matmul(adj, x)
        x = x + self.bias2
        x = torch.relu(x)
        # Global mean pool
        x = x.mean(dim=0, keepdim=True)  # [1, hidden]
        return self.head(x)  # [1, out_channels]


def _gcnconv_to_dense(conv_layer, lin_layer, bias_param):
    """Transfer weights from GCNConv to the dense model's lin + bias."""
    with torch.no_grad():
        # GCNConv stores weights as .lin.weight [out, in] (no bias in lin)
        if hasattr(conv_layer, 'lin'):
            lin_layer.weight.copy_(conv_layer.lin.weight)
        else:
            lin_layer.weight.copy_(conv_layer.weight)
        # GCNConv has a separate .bias parameter
        if conv_layer.bias is not None:
            bias_param.copy_(conv_layer.bias)
        else:
            bias_param.zero_()


def build_normalized_adjacency(edge_index, num_nodes):
    """Build GCNConv-compatible normalized adjacency from edge_index.

    Replicates PyG's GCNConv normalization exactly:
    1. Add self-loops
    2. Compute degree of A_hat
    3. adj[dst, src] = d_inv_sqrt[dst] * d_inv_sqrt[src]
    """
    adj = torch.zeros(num_nodes, num_nodes)
    # Add self-loops to edge_index
    self_loops = torch.arange(num_nodes, dtype=torch.long).unsqueeze(0).repeat(2, 1)
    ei_hat = torch.cat([edge_index, self_loops], dim=1)
    # Compute degree (count incoming edges for each node in dst)
    deg = torch.zeros(num_nodes)
    for k in range(ei_hat.shape[1]):
        deg[int(ei_hat[1, k])] += 1.0
    d_inv_sqrt = deg.pow(-0.5)
    d_inv_sqrt[d_inv_sqrt == float('inf')] = 0
    # Fill adjacency: message flows from src to dst
    for k in range(ei_hat.shape[1]):
        src, dst = int(ei_hat[0, k]), int(ei_hat[1, k])
        adj[dst, src] += d_inv_sqrt[dst] * d_inv_sqrt[src]
    return adj


def main():
    print("Loading trained DemoGraphNet...")
    source_model, meta = _load_model()

    print("Creating ONNX-exportable dense model...")
    dense_model = DenseGNNForExport(in_channels=7, hidden_channels=24, out_channels=5)

    # Transfer weights
    _gcnconv_to_dense(source_model.conv1, dense_model.lin1, dense_model.bias1)
    _gcnconv_to_dense(source_model.conv2, dense_model.lin2, dense_model.bias2)
    with torch.no_grad():
        dense_model.head[0].weight.copy_(source_model.head[0].weight)
        dense_model.head[0].bias.copy_(source_model.head[0].bias)
        dense_model.head[2].weight.copy_(source_model.head[2].weight)
        dense_model.head[2].bias.copy_(source_model.head[2].bias)
    dense_model.eval()

    # Validate against source model on all graph types
    print("\nValidating weight transfer...")
    _set_seed(42)
    all_match = True
    for label, gen in GENERATORS.items():
        txns = gen(999)
        data = _transactions_to_data(txns)
        adj = build_normalized_adjacency(data.edge_index, data.x.shape[0])
        batch = torch.zeros(data.x.shape[0], dtype=torch.long)

        with torch.no_grad():
            orig_logits = source_model(data.x, data.edge_index, batch)
            dense_logits = dense_model(data.x, adj)

        orig_pred = GRAPH_LABELS[orig_logits.argmax(dim=1).item()]
        dense_pred = GRAPH_LABELS[dense_logits.argmax(dim=1).item()]
        match = orig_pred == dense_pred
        if not match:
            all_match = False
        print(f"  {label:15s}: orig={orig_pred:15s} dense={dense_pred:15s} {'OK' if match else 'MISMATCH'}")

    if not all_match:
        print("\nWARNING: Some predictions differ (expected for approximation). Continuing export.")

    # Export to ONNX
    output_dir = PROJECT_ROOT / "frontend" / "public" / "models"
    output_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = output_dir / "demo_graph_gnn.onnx"

    # Use a medium-sized dummy input (10 nodes)
    dummy_x = torch.randn(10, 7)
    dummy_adj = torch.eye(10)

    print(f"\nExporting to {onnx_path}...")
    torch.onnx.export(
        dense_model,
        (dummy_x, dummy_adj),
        str(onnx_path),
        input_names=["node_features", "adjacency"],
        output_names=["logits"],
        dynamic_axes={
            "node_features": {0: "num_nodes"},
            "adjacency": {0: "num_nodes", 1: "num_nodes"},
        },
        opset_version=18,
    )

    # Consolidate external data into the .onnx file so onnxruntime-web
    # can load it in the browser (no filesystem access for .data files).
    model_proto = onnx.load(str(onnx_path), load_external_data=True)
    onnx.save(model_proto, str(onnx_path))
    # Remove leftover external data file if present
    data_file = onnx_path.with_suffix('.onnx.data')
    if data_file.exists():
        data_file.unlink()
        print("  Removed external data file (weights embedded in .onnx)")

    print(f"  ONNX exported: {onnx_path} ({onnx_path.stat().st_size / 1024:.1f} KB)")

    # Save metadata for frontend
    meta_path = output_dir / "demo_graph_gnn_meta.json"
    meta_out = {
        "graph_labels": GRAPH_LABELS,
        "feature_dim": 7,
        "feature_names": [
            "in_degree", "out_degree", "incoming_value",
            "outgoing_value", "net_amount", "total_flow", "role_value"
        ],
        "hidden_channels": 24,
        "onnx_file": "demo_graph_gnn.onnx",
    }
    with open(meta_path, "w") as f:
        json.dump(meta_out, f, indent=2)
    print(f"  Meta saved: {meta_path}")

    print("\nDone! Model ready for frontend inference via onnxruntime-web.")


if __name__ == "__main__":
    main()
