import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Node:
    """Graph node representation."""
    id: str
    type: str
    citation: Optional[str] = None
    tags: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        return cls(
            id=str(data.get("id")),
            type=data.get("type", ""),
            citation=data.get("citation"),
            tags=list(data.get("tags", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "citation": self.citation,
            "tags": self.tags or [],
        }


@dataclass
class Edge:
    """Graph edge representation."""
    source: str
    target: str
    date: Optional[date] = None
    weight: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Edge":
        d = data.get("date")
        edge_date = date.fromisoformat(d) if d else None
        weight_val = data.get("weight")
        weight = float(weight_val) if weight_val is not None else None
        return cls(
            source=str(data["source"]),
            target=str(data["target"]),
            date=edge_date,
            weight=weight,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "date": self.date.isoformat() if self.date else None,
            "weight": self.weight,
        }


def load_graph(path: str | Path) -> Dict[str, List[Dict[str, Any]]]:
    """Load a graph description from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def _normalise_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    nodes = [Node.from_dict(n).to_dict() for n in graph.get("nodes", [])]
    edges = [Edge.from_dict(e).to_dict() for e in graph.get("edges", [])]
    return {"nodes": nodes, "edges": edges}


def search_by_type(graph: Dict[str, Any], node_type: str) -> List[Dict[str, Any]]:
    """Return nodes matching a type."""
    graph = _normalise_graph(graph)
    return [n for n in graph["nodes"] if n.get("type") == node_type]


def search_by_citation(graph: Dict[str, Any], citation: str) -> List[Dict[str, Any]]:
    """Return nodes with a specific citation."""
    graph = _normalise_graph(graph)
    return [n for n in graph["nodes"] if n.get("citation") == citation]


def search_by_tag(graph: Dict[str, Any], tag: str) -> List[Dict[str, Any]]:
    """Return nodes containing a tag."""
    graph = _normalise_graph(graph)
    return [n for n in graph["nodes"] if tag in n.get("tags", [])]


def traverse_edges(
    graph: Dict[str, Any],
    start: str,
    *,
    depth: int = 1,
    since: Optional[date] = None,
    min_weight: Optional[float] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Breadth-first traversal from ``start`` with optional edge filters."""
    graph = _normalise_graph(graph)
    nodes_index = {n["id"]: n for n in graph["nodes"]}
    visited = {start}
    result_edges: List[Dict[str, Any]] = []
    queue: List[tuple[str, int]] = [(start, 0)]
    seen_edges: set[tuple[str, str]] = set()

    while queue:
        current, d = queue.pop(0)
        if d >= depth:
            continue
        for edge in graph["edges"]:
            if edge["source"] != current and edge["target"] != current:
                continue
            edge_date = date.fromisoformat(edge["date"]) if edge.get("date") else None
            if since and edge_date and edge_date < since:
                continue
            if since and edge_date is None:
                continue
            weight = edge.get("weight")
            if min_weight is not None and (weight is None or weight < min_weight):
                continue
            key = (edge["source"], edge["target"])
            if key in seen_edges or (key[1], key[0]) in seen_edges:
                continue
            seen_edges.add(key)
            result_edges.append(edge)
            next_node = edge["target"] if edge["source"] == current else edge["source"]
            if next_node not in visited:
                visited.add(next_node)
                queue.append((next_node, d + 1))

    result_nodes = [nodes_index[n_id] for n_id in visited if n_id in nodes_index]
    return {"nodes": result_nodes, "edges": result_edges}
