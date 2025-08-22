"""Load concept seeds and triggers into the graph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

from ..graph.models import EdgeType, GraphEdge, GraphNode, LegalGraph, NodeType


DATA_DIR = Path(__file__).resolve().parents[2] / "concepts"


def load() -> Tuple[LegalGraph, Dict[str, str]]:
    """Load seed concepts and trigger phrases.

    Returns
    -------
    Tuple[LegalGraph, Dict[str, str]]
        The populated :class:`~SensibLaw.graph.models.LegalGraph` and a
        mapping of trigger phrases to concept identifiers.
    """

    graph = LegalGraph()

    seeds_file = DATA_DIR / "seeds.json"
    if seeds_file.exists():
        with seeds_file.open("r", encoding="utf-8") as fh:
            seeds = json.load(fh)
        for concept in seeds.get("concepts", []):
            graph.add_node(
                GraphNode(
                    type=NodeType.CONCEPT,
                    identifier=concept["id"],
                    metadata={"label": concept.get("label", "")},
                )
            )
        for rel in seeds.get("relations", []):
            edge_type = EdgeType[rel["type"]]
            graph.add_edge(
                GraphEdge(
                    type=edge_type,
                    source=rel["source"],
                    target=rel["target"],
                )
            )

    triggers: Dict[str, str] = {}
    triggers_dir = DATA_DIR / "triggers"
    if triggers_dir.exists():
        for path in triggers_dir.glob("*.json"):
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if "id" in data and "phrases" in data:
                concept_id = data["id"]
                for phrase in data["phrases"]:
                    triggers[phrase.lower()] = concept_id
            else:
                for phrase, concept_id in data.items():
                    triggers[str(phrase).lower()] = str(concept_id)

    return graph, triggers


GRAPH, TRIGGERS = load()


__all__ = ["GRAPH", "TRIGGERS", "load"]
