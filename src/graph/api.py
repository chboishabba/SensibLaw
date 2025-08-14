from __future__ import annotations

"""Serialization helpers for :mod:`SensibLaw.graph`.

This module provides utilities to turn a :class:`~SensibLaw.graph.models.LegalGraph`
into a JSON-serialisable structure.  When requested the edge set is first
reduced using a transitive reduction computed by :mod:`networkx`.  This removes
redundant edges that are implied by transitive paths while preserving the
reachability between nodes.
"""

from dataclasses import asdict
from typing import Dict, Any

import networkx as nx

from .models import LegalGraph


def serialize_graph(graph: LegalGraph, reduced: bool = False) -> Dict[str, Any]:
    """Serialise ``graph`` to a dictionary.

    Parameters
    ----------
    graph:
        The :class:`~SensibLaw.graph.models.LegalGraph` instance to serialise.
    reduced:
        If ``True`` the edges are first subjected to a transitive reduction
        which prunes those that are implied by transitive reachability.
    """

    g = nx.DiGraph()
    for node in graph.nodes.values():
        g.add_node(node.identifier, obj=node)
    for edge in graph.edges:
        g.add_edge(edge.source, edge.target, obj=edge)

    if reduced:
        g = nx.transitive_reduction(g)

    nodes = [asdict(data["obj"]) for _, data in g.nodes(data=True)]
    edges = [asdict(data["obj"]) for _, _, data in g.edges(data=True)]
    return {"nodes": nodes, "edges": edges}


__all__ = ["serialize_graph"]
