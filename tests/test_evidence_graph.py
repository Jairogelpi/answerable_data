from __future__ import annotations

import unittest

from answerable.evidence.graph import EdgeType, EvidenceGraphStore, GraphEdge, GraphNode, NodeType

FR_GRAPH_001 = "FR-GRAPH-001"
FR_GRAPH_002 = "FR-GRAPH-002"
FR_GRAPH_003 = "FR-GRAPH-003"
FR_GRAPH_004 = "FR-GRAPH-004"
FR_GRAPH_005 = "FR-GRAPH-005"
FR_GRAPH_006 = "FR-GRAPH-006"
FR_GRAPH_007 = "FR-GRAPH-007"


class EvidenceGraphTests(unittest.TestCase):
    def graph(self) -> EvidenceGraphStore:
        graph = EvidenceGraphStore()
        graph.add_node(GraphNode("data", NodeType.DATASET, {"fingerprint": "abc"}))
        graph.add_node(GraphNode("fact", NodeType.FACT, {"value": 42}))
        graph.add_node(GraphNode("claim", NodeType.ALLOWED_CLAIM, {"text": "Revenue rose"}))
        graph.add_node(GraphNode("block", NodeType.BLOCKER, {"reason": "missing period"}))
        graph.add_edge(GraphEdge("claim", "fact", EdgeType.SUPPORTS))
        graph.add_edge(GraphEdge("fact", "data", EdgeType.COMPUTED_FROM))
        graph.add_edge(GraphEdge("block", "data", EdgeType.BLOCKS))
        graph.add_edge(GraphEdge("fact", "block", EdgeType.CONTRADICTS))
        return graph

    def test_phase_13_validates_claim_provenance_and_stable_export(self) -> None:
        graph = self.graph()
        graph.validate_claims()
        first = graph.export()
        second = graph.export()
        self.assertEqual(first, second)
        self.assertEqual(len(first["content_hash"]), 64)
        self.assertIn("data", {node.node_id for node in graph.source_context("claim")})

    def test_phase_13_rejects_cycles_missing_endpoints_and_unproven_claims(self) -> None:
        graph = self.graph()
        with self.assertRaises(ValueError):
            graph.add_edge(GraphEdge("data", "claim", EdgeType.DEPENDS_ON))
        with self.assertRaises(ValueError):
            graph.add_edge(GraphEdge("missing", "data", EdgeType.USES))
        orphan = EvidenceGraphStore()
        orphan.add_node(GraphNode("claim", NodeType.ALLOWED_CLAIM, {}))
        with self.assertRaises(ValueError):
            orphan.validate_claims()

    def test_phase_13_reduced_graph_keeps_blocker_paths_and_contradiction(self) -> None:
        graph = self.graph()
        reduced = {node.node_id for node in graph.reduced()}
        self.assertEqual(reduced, {"block", "claim", "data"})
        exported_edges = graph.export()["edges"]
        self.assertIn("contradicts", {edge["type"] for edge in exported_edges})


if __name__ == "__main__":
    unittest.main()
