from __future__ import annotations

import re
from typing import Dict, Iterable, List, Mapping, Tuple, Union

from src.models.document import Document
from src.obligation_identity import compute_identities
from src.obligations import ObligationAtom, extract_obligations_from_document, extract_obligations_from_text

CROSSDOC_VERSION = "obligation.crossdoc.v1"

EDGE_PATTERNS: Dict[str, re.Pattern] = {
    "supersedes": re.compile(
        r"\b(repeals?|revokes?|supersede[sd]?|supersedes?|has effect instead of|ceases to have effect)\b", re.IGNORECASE
    ),
    "conflicts_with": re.compile(
        r"\b(inconsistent with|despite any other provision|to the extent of any inconsistency)\b", re.IGNORECASE
    ),
    "exception_to": re.compile(
        r"\b(except as provided in|does not apply to|this (?:section|regulation) does not apply)\b", re.IGNORECASE
    ),
    "applies_despite": re.compile(r"\bdespite (?:section|regulation|anything in)\b", re.IGNORECASE),
    "applies_subject_to": re.compile(r"\bsubject to (?:section|regulation|this act)\b", re.IGNORECASE),
}

FORBIDDEN_PHRASES = re.compile(
    r"\b(having regard to|consistent with|guided by|for the purposes of|as if|taken to)\b", re.IGNORECASE
)


def _collect_nodes(obligations: Iterable[ObligationAtom], source_id: str) -> List[dict]:
    identities = compute_identities(obligations)
    return [
        {"obl_id": oid.identity_hash, "source_id": source_id, "clause_id": ob.clause_id}
        for oid, ob in zip(identities, obligations)
    ]


def _clause_text(full_text: str, obligation: ObligationAtom) -> str:
    """Best-effort clause slice; falls back to full text if spans are missing."""
    if not obligation.span:
        return full_text
    start, end = obligation.span
    return " ".join(full_text.split()[start:end]) or full_text


def _find_edges(
    full_text: str,
    source_id: str,
    obligations: Iterable[ObligationAtom],
    ref_target_map: Mapping[str, List[Tuple[str, str]]],
) -> List[dict]:
    """
    Detect explicit cross-document edges inside a single document.
    Rules (Sprint 7B): explicit phrase + explicit reference identities required.
    Forbidden phrases short-circuit edge emission.
    """

    edges: List[dict] = []
    if FORBIDDEN_PHRASES.search(full_text or ""):
        return edges

    for ob, oid in zip(obligations, compute_identities(obligations)):
        if not ob.reference_identities:
            continue  # cannot emit edge without explicit reference identity
        clause_text = _clause_text(full_text or "", ob).lower()
        for kind, pattern in EDGE_PATTERNS.items():
            match = pattern.search(clause_text)
            if not match:
                continue
            matched_text = match.group(0)
            for ref_id in ob.reference_identities:
                candidates = ref_target_map.get(ref_id, [])
                target_ob = next((oid for oid, sid in candidates if sid != source_id), None)
                if target_ob is None and candidates:
                    target_ob = candidates[0][0]  # fallback to any deterministic target
                if not target_ob:
                    continue  # hard precondition: reference must resolve to an obligation
                edges.append(
                    {
                        "kind": kind,
                        "from": oid.identity_hash,
                        "to": target_ob,
                        "text": matched_text,
                        "provenance": {
                            "source_id": source_id,
                            "clause_id": ob.clause_id,
                        },
                    }
                )
    return edges


def _extract_obligations(source_id: str, payload: Union[str, Document]) -> Iterable[ObligationAtom]:
    if isinstance(payload, Document):
        return extract_obligations_from_document(payload)
    return extract_obligations_from_text(str(payload), source_id=source_id)


def build_crossdoc_topology(documents: Mapping[str, Union[str, Document]]) -> dict:
    """
    Build a cross-document graph payload from source texts or Document objects.
    Only explicit clause-local references plus edge phrases produce edges.
    """

    nodes: List[dict] = []
    edges: List[dict] = []
    doc_entries: List[Tuple[str, str, List[ObligationAtom]]] = []

    for source_id, raw in sorted(documents.items(), key=lambda kv: kv[0]):
        obligations = list(_extract_obligations(source_id, raw))
        text = raw.body if isinstance(raw, Document) else str(raw)
        nodes.extend(_collect_nodes(obligations, source_id))
        doc_entries.append((source_id, text, obligations))

    ref_target_map: Dict[str, List[Tuple[str, str]]] = {}
    for _, _, obligations in doc_entries:
        identities = compute_identities(obligations)
        for ob, oid in zip(obligations, identities):
            for ref_id in ob.reference_identities:
                ref_target_map.setdefault(ref_id, []).append((oid.identity_hash, ob.clause_id.rsplit("-clause-", 1)[0]))

    for source_id, text, obligations in doc_entries:
        edges.extend(_find_edges(text, source_id, obligations, ref_target_map))

    edges_sorted = sorted(edges, key=lambda e: (e["kind"], e["from"], e["to"], e["text"]))
    nodes_sorted = sorted(nodes, key=lambda n: n["obl_id"])

    return {
        "version": CROSSDOC_VERSION,
        "nodes": nodes_sorted,
        "edges": edges_sorted,
    }


__all__ = ["build_crossdoc_topology", "CROSSDOC_VERSION"]
