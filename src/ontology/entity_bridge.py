from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any

from src.text.lexeme_index import LexemeOccurrence


@dataclass(frozen=True, slots=True)
class ExternalEntityLink:
    canonical_ref: str
    canonical_kind: str
    provider: str
    external_id: str
    curie: str


_BRIDGE = {
    ("institution_ref", "institution:united_nations"): ("wikidata", "Q1065"),
    ("institution_ref", "institution:united_nations_security_council"): ("wikidata", "Q37470"),
    ("court_ref", "court:international_criminal_court"): ("wikidata", "Q47488"),
    ("court_ref", "court:international_court_of_justice"): ("wikidata", "Q7801"),
}


def link_canonical_ref(norm_text: str, kind: str) -> ExternalEntityLink | None:
    hit = _BRIDGE.get((kind, norm_text))
    if hit is None:
        return None
    provider, external_id = hit
    return ExternalEntityLink(
        canonical_ref=norm_text,
        canonical_kind=kind,
        provider=provider,
        external_id=external_id,
        curie=f"{provider}:{external_id}",
    )


def link_lexeme_occurrences(occurrences: Iterable[LexemeOccurrence]) -> list[ExternalEntityLink]:
    out: list[ExternalEntityLink] = []
    seen: set[tuple[str, str, str]] = set()
    for occ in occurrences:
        linked = link_canonical_ref(occ.norm_text, occ.kind)
        if linked is None:
            continue
        key = (linked.canonical_ref, linked.provider, linked.external_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(linked)
    return out


def build_external_refs_batch(
    occurrences: Iterable[LexemeOccurrence],
    anchor_map: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    actor_external_refs: list[dict[str, Any]] = []
    concept_external_refs: list[dict[str, Any]] = []
    for linked in link_lexeme_occurrences(occurrences):
        anchor = anchor_map.get(linked.canonical_ref)
        if not anchor:
            continue
        base = {
            "provider": linked.provider,
            "external_id": linked.external_id,
            "external_url": f"https://www.wikidata.org/wiki/{linked.external_id}" if linked.provider == "wikidata" else None,
            "notes": f"bridge canonical_ref={linked.canonical_ref} canonical_kind={linked.canonical_kind}",
        }
        if "actor_id" in anchor:
            row = dict(base)
            row["actor_id"] = int(anchor["actor_id"])
            actor_external_refs.append(row)
        elif "concept_code" in anchor:
            row = dict(base)
            row["concept_code"] = str(anchor["concept_code"])
            concept_external_refs.append(row)
    return {
        "meta": {
            "source": "entity_bridge",
            "bridge_refs": [link.canonical_ref for link in link_lexeme_occurrences(occurrences)],
        },
        "concept_external_refs": concept_external_refs,
        "actor_external_refs": actor_external_refs,
    }


__all__ = [
    "ExternalEntityLink",
    "build_external_refs_batch",
    "link_canonical_ref",
    "link_lexeme_occurrences",
]
