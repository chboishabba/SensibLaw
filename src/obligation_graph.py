from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Set

from src.obligations import ObligationAtom, ConditionAtom
from src.obligation_identity import ObligationIdentity, compute_identities


@dataclass(frozen=True)
class ObligationGraph:
    nodes: List[ObligationIdentity]
    conditional_on: List[tuple[str, str]]  # obligation_hash -> condition_type
    exception_to: List[tuple[str, str]]  # obligation_hash -> condition_type


def build_obligation_graph(obligations: Iterable[ObligationAtom]) -> ObligationGraph:
    identities = compute_identities(obligations)
    id_map: Dict[str, ObligationIdentity] = {o.identity_hash: o for o in identities}
    cond_edges: List[tuple[str, str]] = []
    exc_edges: List[tuple[str, str]] = []
    for identity, ob in zip(identities, obligations):
        for cond in ob.conditions:
            if cond.type in {"if", "subject", "provided", "when", "where", "until", "upon"}:
                cond_edges.append((identity.identity_hash, cond.type))
            elif cond.type in {"unless", "except"}:
                exc_edges.append((identity.identity_hash, cond.type))
    return ObligationGraph(nodes=list(id_map.values()), conditional_on=cond_edges, exception_to=exc_edges)


def obligations_for(reference_identity: str, graph: ObligationGraph) -> List[ObligationIdentity]:
    return [node for node in graph.nodes if reference_identity in node.reference_hashes]


def obligations_triggered_by(facts: Set[str]) -> List[ObligationIdentity]:
    """Placeholder hook for compliance checks; currently deterministic no-op."""
    return []


__all__ = [
    "ObligationGraph",
    "build_obligation_graph",
    "obligations_for",
    "obligations_triggered_by",
]
