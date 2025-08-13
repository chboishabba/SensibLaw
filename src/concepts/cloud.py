"""Concept cloud construction utilities.

Provides ``build_cloud`` to assemble a subgraph around given concept hits
and ``score_node`` to rank nodes based on heuristic signals.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Tuple

from ..graph.models import GraphEdge, GraphNode, LegalGraph


def score_node(node: GraphNode, signals: Dict[str, Any]) -> float:
    """Score a node based on heuristic signals.

    Parameters
    ----------
    node:
        The :class:`~SensibLaw.graph.models.GraphNode` being scored.
    signals:
        Mapping of signal names to values, such as ``keyword_exact`` (bool or
        float), ``jurisdiction_match`` (bool), ``court_rank`` (numeric), etc.

    Returns
    -------
    float
        Aggregate score between 0 and 1.
    """

    weights = {
        "keyword_exact": 0.4,
        "jurisdiction_match": 0.2,
        "recency": 0.2,
        "court_rank": 0.2,
    }
    score = 0.0

    # Keyword exactness
    exact = signals.get("keyword_exact", False)
    if isinstance(exact, bool):
        exact = 1.0 if exact else 0.0
    score += weights["keyword_exact"] * float(exact)

    # Jurisdiction alignment
    juris = signals.get("jurisdiction_match", False)
    if isinstance(juris, bool):
        juris = 1.0 if juris else 0.0
    score += weights["jurisdiction_match"] * float(juris)

    # Recency based on node date
    if node.date:
        days_old = (date.today() - node.date).days
        recency_score = 1 / (1 + days_old / 365)
        score += weights["recency"] * recency_score

    # Court rank (higher value => higher score)
    court_rank = signals.get("court_rank")
    if court_rank is not None:
        try:
            court_score = float(court_rank)
            # Normalise assuming ranks 1 (lowest) upwards; invert so higher
            # ranks yield higher scores.
            court_score = 1 / (1 + court_score)
            score += weights["court_rank"] * court_score
        except (TypeError, ValueError):
            pass

    return score


def build_cloud(
    concept_hits: Iterable[Tuple[str, Dict[str, Any]]],
    graph: LegalGraph,
    limit: int = 50,
) -> Dict[str, Any]:
    """Build a concept cloud around the provided hits.

    Parameters
    ----------
    concept_hits:
        Iterable of ``(node_id, signals)`` tuples representing candidate
        nodes in the graph along with their associated signals.
    graph:
        The :class:`~SensibLaw.graph.models.LegalGraph` from which to pull
        related nodes and edges.
    limit:
        Maximum number of primary hit nodes to include.

    Returns
    -------
    Dict[str, Any]
        JSON-serialisable representation containing ``nodes``, ``edges`` and
        ``scores`` suitable for downstream proof-tree rendering.
    """

    scored: List[Tuple[float, GraphNode]] = []
    for node_id, signals in concept_hits:
        node = graph.get_node(node_id)
        if not node:
            continue
        score = score_node(node, signals)
        scored.append((score, node))

    scored.sort(key=lambda x: x[0], reverse=True)
    scored = scored[:limit]

    nodes: Dict[str, GraphNode] = {}
    scores: Dict[str, float] = {}
    for score, node in scored:
        nodes[node.identifier] = node
        scores[node.identifier] = score

    edge_map: Dict[Tuple[str, str, str], GraphEdge] = {}
    for node_id in list(nodes.keys()):
        for edge in graph.find_edges(source=node_id):
            edge_map[(edge.source, edge.target, edge.type.value)] = edge
            other = edge.target
            if other not in nodes:
                other_node = graph.get_node(other)
                if other_node:
                    nodes[other] = other_node
                    scores.setdefault(other, 0.0)
        for edge in graph.find_edges(target=node_id):
            edge_map[(edge.source, edge.target, edge.type.value)] = edge
            other = edge.source
            if other not in nodes:
                other_node = graph.get_node(other)
                if other_node:
                    nodes[other] = other_node
                    scores.setdefault(other, 0.0)

    serialisable_nodes = [
        {
            "id": n.identifier,
            "type": n.type.value,
            "metadata": n.metadata,
            "date": n.date.isoformat() if n.date else None,
        }
        for n in nodes.values()
    ]

    serialisable_edges = [
        {
            "source": e.source,
            "target": e.target,
            "type": e.type.value,
            "metadata": e.metadata,
            "weight": e.weight,
            "date": e.date.isoformat() if e.date else None,
        }
        for e in edge_map.values()
    ]

    return {"nodes": serialisable_nodes, "edges": serialisable_edges, "scores": scores}


__all__ = ["build_cloud", "score_node"]
