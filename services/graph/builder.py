"""
Graph-based fraud detection for Intelli-Credit.
Builds transaction graphs from DuckDB data and detects circular trading
using motif analysis (NetworkX primary, PyG fallback for FLAG GNN).
"""
import json
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

try:
    import networkx as nx
except ImportError:
    nx = None


@dataclass
class FraudAlert:
    """A detected fraud indicator."""
    alert_type: str  # cycle, star_seller, dense_cluster, chain_motif
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    entities: list[str] = field(default_factory=list)
    description: str = ""
    risk_score: float = 0.0
    evidence: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)


class TransactionGraphBuilder:
    """Builds and analyzes transaction graphs for fraud detection."""

    def __init__(self):
        if nx is None:
            raise ImportError("networkx required: pip install networkx")
        self.graph = nx.DiGraph()

    def add_transaction(self, source: str, target: str, amount: float,
                        date: str = None, txn_type: str = None,
                        metadata: dict = None) -> None:
        """Add a transaction edge to the graph."""
        if self.graph.has_edge(source, target):
            # Aggregate edge weights
            self.graph[source][target]['weight'] += amount
            self.graph[source][target]['count'] += 1
            self.graph[source][target]['transactions'].append({
                'amount': amount, 'date': date, 'type': txn_type
            })
        else:
            self.graph.add_edge(source, target, weight=amount, count=1,
                                transactions=[{'amount': amount, 'date': date, 'type': txn_type}])

        # Ensure node attributes
        for node in [source, target]:
            if 'entity_type' not in self.graph.nodes[node]:
                self.graph.nodes[node]['entity_type'] = 'unknown'
            if metadata:
                self.graph.nodes[node].update(metadata.get(node, {}))

    def detect_cycles(self, min_length: int = 3, max_length: int = 8,
                      min_value: float = 500000) -> list[FraudAlert]:
        """Detect circular trading patterns (cycles in the graph)."""
        alerts = []

        try:
            cycles = list(nx.simple_cycles(self.graph))
        except Exception:
            cycles = []

        for cycle in cycles:
            if min_length <= len(cycle) <= max_length:
                # Calculate cycle value
                total_value = 0
                for i in range(len(cycle)):
                    src = cycle[i]
                    tgt = cycle[(i + 1) % len(cycle)]
                    if self.graph.has_edge(src, tgt):
                        total_value += self.graph[src][tgt].get('weight', 0)

                if total_value >= min_value:
                    alert = FraudAlert(
                        alert_type="cycle",
                        severity="CRITICAL",
                        entities=cycle,
                        description=f"Circular trading chain of {len(cycle)} entities "
                                    f"with total value ₹{total_value:,.0f}",
                        risk_score=min(1.0, total_value / 10000000),  # Normalize
                        evidence={
                            "cycle_length": len(cycle),
                            "total_value": total_value,
                            "entities": cycle,
                        },
                        provenance={
                            "extraction_method": "networkx_cycle_detection",
                            "agent_id": "graph-fraud-detector",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    alerts.append(alert)

        return alerts

    def detect_star_sellers(self, min_out_degree: int = 10,
                            max_lifespan_days: int = 90) -> list[FraudAlert]:
        """Detect star seller patterns (hub nodes with many buyers)."""
        alerts = []

        for node in self.graph.nodes():
            out_degree = self.graph.out_degree(node)
            if out_degree >= min_out_degree:
                total_issued = sum(
                    self.graph[node][succ].get('weight', 0)
                    for succ in self.graph.successors(node)
                )
                alert = FraudAlert(
                    alert_type="star_seller",
                    severity="HIGH",
                    entities=[node],
                    description=f"Star seller {node}: {out_degree} buyers, "
                                f"₹{total_issued:,.0f} total issued",
                    risk_score=min(1.0, out_degree / 50),
                    evidence={
                        "out_degree": out_degree,
                        "total_issued": total_issued,
                        "buyers": list(self.graph.successors(node)),
                    },
                    provenance={
                        "extraction_method": "networkx_star_detection",
                        "agent_id": "graph-fraud-detector",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                alerts.append(alert)

        return alerts

    def compute_centrality(self) -> dict:
        """Compute centrality metrics for all nodes."""
        metrics = {}

        try:
            pagerank = nx.pagerank(self.graph, weight='weight')
        except Exception:
            node_count = max(1, self.graph.number_of_nodes())
            pagerank = {
                node: (self.graph.in_degree(node) + self.graph.out_degree(node)) / node_count
                for node in self.graph.nodes()
            }
        try:
            hubs, authorities = nx.hits(self.graph)
        except Exception:
            hubs = {n: 0.0 for n in self.graph.nodes()}
            authorities = {n: 0.0 for n in self.graph.nodes()}

        degree_centrality = nx.degree_centrality(self.graph)
        betweenness = nx.betweenness_centrality(self.graph)

        for node in self.graph.nodes():
            metrics[node] = {
                "pagerank": pagerank.get(node, 0),
                "hub_score": hubs.get(node, 0),
                "authority_score": authorities.get(node, 0),
                "degree_centrality": degree_centrality.get(node, 0),
                "betweenness_centrality": betweenness.get(node, 0),
            }

        return metrics

    def detect_dense_clusters(self, min_density: float = 0.7,
                              min_size: int = 3) -> list[FraudAlert]:
        """Detect densely connected subgraphs (potential fraud rings)."""
        alerts = []

        # Use undirected version for community detection
        undirected = self.graph.to_undirected()

        for component in nx.connected_components(undirected):
            if len(component) >= min_size:
                subgraph = undirected.subgraph(component)
                density = nx.density(subgraph)

                if density >= min_density:
                    entities = list(component)
                    alert = FraudAlert(
                        alert_type="dense_cluster",
                        severity="HIGH",
                        entities=entities,
                        description=f"Dense cluster of {len(entities)} entities "
                                    f"with density {density:.2f}",
                        risk_score=density,
                        evidence={
                            "cluster_size": len(entities),
                            "density": density,
                            "entities": entities,
                        },
                        provenance={
                            "extraction_method": "networkx_cluster_detection",
                            "agent_id": "graph-fraud-detector",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    alerts.append(alert)

        return alerts

    def run_all_detections(self) -> list[FraudAlert]:
        """Run all fraud detection algorithms."""
        alerts = []
        alerts.extend(self.detect_cycles())
        alerts.extend(self.detect_star_sellers())
        alerts.extend(self.detect_dense_clusters())
        return alerts

    def to_topology_dict(self) -> dict:
        """Serialize full graph topology for API/D3 visualization."""
        centrality = self.compute_centrality()
        nodes = []
        for node in self.graph.nodes():
            attrs = self.graph.nodes[node]
            metrics = centrality.get(node, {})
            nodes.append({
                "id": node,
                "role": attrs.get("role", attrs.get("entity_type", "unknown")),
                "in_degree": self.graph.in_degree(node),
                "out_degree": self.graph.out_degree(node),
                "pagerank": round(metrics.get("pagerank", 0), 6),
                "betweenness": round(metrics.get("betweenness_centrality", 0), 6),
                "hub_score": round(metrics.get("hub_score", 0), 6),
                "authority_score": round(metrics.get("authority_score", 0), 6),
            })
        edges = []
        for source, target, attrs in self.graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "weight": attrs.get("weight", 0),
                "count": attrs.get("count", 1),
                "transactions": attrs.get("transactions", []),
            })
        return {"nodes": nodes, "edges": edges}

    def get_node_count(self) -> int:
        return self.graph.number_of_nodes()

    def get_edge_count(self) -> int:
        return self.graph.number_of_edges()
