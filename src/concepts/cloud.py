"""Concept cloud construction utilities.

Provides ``build_cloud`` to assemble a subgraph around given concept hits
and ``score_node`` to rank nodes based on heuristic signals.
"""

from __future__ import annotations

from datetime import date
import math
import random
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


def layout_cloud(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    iterations: int = 50,
) -> Dict[str, Dict[str, float]]:
    """Assign 3D coordinates to nodes using a simple force-directed layout.

    The algorithm is a basic Fruchterman-Reingold implementation operating in
    three dimensions. Only the first 300 nodes are considered to keep
    computation tractable.

    Parameters
    ----------
    nodes:
        List of node dictionaries each containing an ``id`` key.
    edges:
        List of edge dictionaries with ``source`` and ``target`` keys.
    iterations:
        Number of relaxation steps to run.

    Returns
    -------
    Dict[str, Dict[str, float]]
        Mapping of node identifiers to ``{"x", "y", "z"}`` coordinate
        dictionaries.
    """

    if not nodes:
        return {}

    max_nodes = 300
    if len(nodes) > max_nodes:
        allowed = {n["id"] for n in nodes[:max_nodes]}
        nodes = [n for n in nodes if n["id"] in allowed]
        edges = [e for e in edges if e["source"] in allowed and e["target"] in allowed]

    # Initial random positions within unit cube centred at origin
    pos = {n["id"]: [random.uniform(-0.5, 0.5) for _ in range(3)] for n in nodes}

    volume = 1.0  # unit cube
    k = (volume / len(pos)) ** (1 / 3)

    for i in range(iterations):
        disp = {v: [0.0, 0.0, 0.0] for v in pos}

        # Repulsive forces
        for v in pos:
            for u in pos:
                if u == v:
                    continue
                delta = [pos[v][j] - pos[u][j] for j in range(3)]
                dist = math.sqrt(sum(d * d for d in delta)) + 1e-9
                force = k * k / dist
                for j in range(3):
                    disp[v][j] += (delta[j] / dist) * force

        # Attractive forces
        for e in edges:
            src, tgt = e["source"], e["target"]
            if src not in pos or tgt not in pos:
                continue
            delta = [pos[src][j] - pos[tgt][j] for j in range(3)]
            dist = math.sqrt(sum(d * d for d in delta)) + 1e-9
            force = (dist * dist) / k
            for j in range(3):
                disp[src][j] -= (delta[j] / dist) * force
                disp[tgt][j] += (delta[j] / dist) * force

        # Cool temperature as layout stabilises
        t = 1.0 / (i + 1)
        for v in pos:
            d = math.sqrt(sum(dd * dd for dd in disp[v])) + 1e-9
            step = min(d, t)
            for j in range(3):
                pos[v][j] += (disp[v][j] / d) * step

    # Centre coordinates around origin
    cx = sum(p[0] for p in pos.values()) / len(pos)
    cy = sum(p[1] for p in pos.values()) / len(pos)
    cz = sum(p[2] for p in pos.values()) / len(pos)
    for p in pos.values():
        p[0] -= cx
        p[1] -= cy
        p[2] -= cz

    return {n: {"x": p[0], "y": p[1], "z": p[2]} for n, p in pos.items()}


def build_cloud(
    concept_hits: Iterable[Tuple[str, Any]],
    graph: LegalGraph,
    limit: int = 50,
    precompute_layout: bool = False,
) -> Dict[str, Any]:
    """Build a concept cloud around the provided hits.

    ``concept_hits`` may either be an iterable of ``(node_id, signals)``
    tuples where ``signals`` is a mapping used for scoring, or the raw output
    from :func:`~src.concepts.matcher.ConceptMatcher.match` where each item is
    ``(node_id, (start, end))``.  In the latter case a default ``signals``
    mapping is constructed so that matcher results can be fed directly into
    this function.

    Parameters
    ----------
    concept_hits:
        Iterable of hit tuples describing candidate nodes.
    graph:
        The :class:`~SensibLaw.graph.models.LegalGraph` from which to pull
        related nodes and edges.
    limit:
        Maximum number of primary hit nodes to include.
    precompute_layout:
        If ``True`` compute deterministic layout coordinates based on node
        degree/centrality instead of running the randomised force-directed
        layout.  This can be useful for tests or environments where
        determinism is required.

    Returns
    -------
    Dict[str, Any]
        JSON-serialisable representation containing ``nodes``, ``edges`` and
        ``scores`` suitable for downstream proof-tree rendering.
    """

    scored: List[Tuple[float, GraphNode]] = []
    for node_id, data in concept_hits:
        if isinstance(data, dict):
            signals = data
        else:  # assume matcher ``span`` tuple
            signals = {"span": data, "keyword_exact": True}
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

    max_nodes = 300
    if len(nodes) > max_nodes:
        allowed_ids = set(list(nodes.keys())[:max_nodes])
        nodes = {nid: nodes[nid] for nid in allowed_ids}
        scores = {nid: scores[nid] for nid in allowed_ids}
        edge_map = {
            k: e
            for k, e in edge_map.items()
            if e.source in allowed_ids and e.target in allowed_ids
        }

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

    if precompute_layout:
        # Deterministic layout based on degree and normalised centrality
        degrees: Dict[str, int] = {n["id"]: 0 for n in serialisable_nodes}
        for e in serialisable_edges:
            degrees[e["source"]] += 1
            degrees[e["target"]] += 1
        max_deg = max(degrees.values()) or 1
        for idx, n in enumerate(serialisable_nodes):
            deg = degrees[n["id"]]
            centrality = deg / max_deg
            n.update({"x": float(deg), "y": float(centrality), "z": float(idx)})
    else:
        coords = layout_cloud(serialisable_nodes, serialisable_edges)
        for n in serialisable_nodes:
            coord = coords.get(n["id"])
            if coord:
                n.update(coord)

    return {"nodes": serialisable_nodes, "edges": serialisable_edges, "scores": scores}


__all__ = ["build_cloud", "score_node", "layout_cloud"]
