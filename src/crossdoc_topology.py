from __future__ import annotations

import re
from typing import Dict, Iterable, List, Mapping, Tuple

from src.obligation_identity import compute_identities
from src.obligations import ObligationAtom, extract_obligations_from_text

CROSSDOC_VERSION = "obligation.crossdoc.v1"

EDGE_PATTERNS: Dict[str, re.Pattern] = {
    "supersedes": re.compile(r"\b(supersedes|replaces|is substituted for|takes the place of)\b", re.IGNORECASE),
    "repeals": re.compile(r"\b(repeals?|revokes?)\b", re.IGNORECASE),
    "ceases_under": re.compile(r"\b(ceases to have effect|ceases to apply|has no effect)\b", re.IGNORECASE),
    "applies_instead_of": re.compile(r"\b(applies instead of|in place of|rather than)\b", re.IGNORECASE),
}

FORBIDDEN_PHRASES = re.compile(r"\b(subject to|despite|except|unless|without limiting)\b", re.IGNORECASE)

DISALLOWED_EDGE_TYPES = {"repeals"}  # mapped to supersedes semantics; emitted as supersedes


def _norm(text: str) -> str:
    return text.lower().strip()


def _collect_nodes(obligations: Iterable[ObligationAtom]) -> List[str]:
    return [oid.identity_hash for oid in compute_identities(obligations)]


def _find_edges(text: str, obligations: Iterable[ObligationAtom]) -> List[dict]:
    """
    Detect explicit cross-document edges inside a single document.
    Rules (Sprint 7B phase 1):
    - Edge phrases must be explicit (regex above).
    - Clause must reference another obligation (reference_identities populated).
    - If no reference identities exist, emit no edge (prevents inference).
    - Forbidden phrases short-circuit (no edge).
    """

    edges: List[dict] = []
    if FORBIDDEN_PHRASES.search(text or ""):
        return edges

    for ob in obligations:
        if not ob.reference_identities:
            continue  # cannot emit edge without explicit reference identity
        lower_clause = (text or "").lower()
        for edge_type, pattern in EDGE_PATTERNS.items():
            if not pattern.search(lower_clause):
                continue
            for ref_id in ob.reference_identities:
                edges.append(
                    {
                        "from": compute_identities([ob])[0].identity_hash,
                        "to": ref_id,
                        "type": "supersedes" if edge_type == "repeals" else edge_type,
                        "basis": {
                            "document": ob.clause_id.rsplit("-clause-", 1)[0],
                            "text_span": [0, 0],  # placeholder until span plumbing is added
                            "reference_id": ref_id,
                        },
                        "effective_from": None,
                        "effective_to": None,
                    }
                )
    return edges


def build_crossdoc_topology(documents: Mapping[str, str]) -> dict:
    """
    Build a cross-document graph payload from source texts.
    Current behavior: collects obligation nodes across documents and emits no edges
    until explicit textual citations are parsed in a later step.
    """

    nodes: List[str] = []
    edges: List[dict] = []
    for source_id, text in sorted(documents.items(), key=lambda kv: kv[0]):
        obligations = extract_obligations_from_text(text, source_id=source_id)
        nodes.extend(_collect_nodes(obligations))
        edges.extend(_find_edges(text, obligations))

    return {
        "version": CROSSDOC_VERSION,
        "nodes": sorted(nodes),
        "edges": edges,  # already deterministic (empty)
    }


__all__ = ["build_crossdoc_topology", "CROSSDOC_VERSION"]
