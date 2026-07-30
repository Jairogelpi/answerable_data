from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum


class NodeType(StrEnum):
    QUESTION = "question"
    DATASET = "dataset"
    EXECUTION = "execution"
    OBSERVATION = "observation"
    FACT = "fact"
    ASSUMPTION = "assumption"
    INFERENCE = "inference"
    BLOCKER = "blocker"
    WARNING = "warning"
    ALLOWED_CLAIM = "allowed_claim"
    FORBIDDEN_CLAIM = "forbidden_claim"
    RECOMMENDATION = "recommendation"
    WARRANT = "warrant"


class EdgeType(StrEnum):
    USES = "uses"
    COMPUTED_FROM = "computed_from"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    BLOCKS = "blocks"
    DEPENDS_ON = "depends_on"
    ASSUMES = "assumes"
    SUPERSEDES = "supersedes"
    GENERATED_BY = "generated_by"


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    node_type: NodeType
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType


class EvidenceGraphStore:
    VERSION = "1.0"
    _SOURCES = frozenset(
        {NodeType.DATASET, NodeType.EXECUTION, NodeType.OBSERVATION, NodeType.FACT}
    )
    _CLAIMS = frozenset({NodeType.ALLOWED_CLAIM, NodeType.RECOMMENDATION})

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> None:
        if not node.node_id or node.node_id in self._nodes:
            raise ValueError("node id must be non-empty and unique")
        self._nodes[node.node_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            raise ValueError("edge endpoints must exist")
        if edge in self._edges:
            raise ValueError("duplicate edge")
        self._edges.append(edge)
        if self._has_cycle():
            self._edges.pop()
            raise ValueError("provenance cycles are forbidden")

    def validate_claims(self) -> None:
        for node in self._nodes.values():
            if node.node_type in self._CLAIMS and not self._reaches_source(node.node_id):
                raise ValueError(f"claim has no provenance path: {node.node_id}")

    def source_context(self, node_id: str) -> tuple[GraphNode, ...]:
        if node_id not in self._nodes:
            raise KeyError(node_id)
        reachable = self._reachable(node_id)
        return tuple(
            sorted((self._nodes[item] for item in reachable), key=lambda node: node.node_id)
        )

    def reduced(self) -> tuple[GraphNode, ...]:
        keep = {
            node.node_id
            for node in self._nodes.values()
            if node.node_type in self._CLAIMS | {NodeType.BLOCKER}
        }
        for blocker in tuple(keep):
            if self._nodes[blocker].node_type is NodeType.BLOCKER:
                keep.update(self._reachable(blocker))
        return tuple(self._nodes[item] for item in sorted(keep))

    def export(self) -> dict[str, object]:
        payload = {
            "version": self.VERSION,
            "nodes": [
                {"id": n.node_id, "type": n.node_type.value, "payload": n.payload}
                for n in sorted(self._nodes.values(), key=lambda item: item.node_id)
            ],
            "edges": [
                {"source": e.source_id, "target": e.target_id, "type": e.edge_type.value}
                for e in sorted(
                    self._edges,
                    key=lambda item: (item.source_id, item.target_id, item.edge_type.value),
                )
            ],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return {**payload, "content_hash": hashlib.sha256(canonical.encode()).hexdigest()}

    def _reachable(self, start: str) -> set[str]:
        adjacency: dict[str, set[str]] = {}
        for edge in self._edges:
            adjacency.setdefault(edge.source_id, set()).add(edge.target_id)
        seen: set[str] = set()
        pending = list(adjacency.get(start, ()))
        while pending:
            node = pending.pop()
            if node not in seen:
                seen.add(node)
                pending.extend(adjacency.get(node, ()))
        return seen

    def _reaches_source(self, start: str) -> bool:
        return any(self._nodes[item].node_type in self._SOURCES for item in self._reachable(start))

    def _has_cycle(self) -> bool:
        return any(node_id in self._reachable(node_id) for node_id in self._nodes)
