"""Project bounded external lookup work from local compiler artifacts."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from src.ontology.external_enrichment import ExternalLookupDemand


EXTERNAL_LOOKUP_PROJECTION_REF = "pnf-external-lookup-projection:v0_1"
_ENTITY_FAMILIES = frozenset({"entity", "location", "organization", "person", "class", "role"})


def _mention_rows(artifacts: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    licensing = artifacts.get("licensing")
    if not isinstance(licensing, Mapping):
        return {}
    return {
        str(row.get("mention_ref") or ""): row
        for row in licensing.get("mentions") or ()
        if isinstance(row, Mapping) and row.get("mention_ref")
    }


def _factor_rows(artifacts: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    graph = artifacts.get("refined_pnf_graph") or artifacts.get("pnf_graph") or {}
    if not isinstance(graph, Mapping):
        return {}
    return {
        str(row.get("factor_ref") or ""): row
        for row in graph.get("factors") or ()
        if isinstance(row, Mapping) and row.get("factor_ref")
    }


def _local_type_refs(factor: Mapping[str, Any]) -> tuple[str, ...]:
    refs: set[str] = set()
    for alternative in factor.get("alternatives") or ():
        if not isinstance(alternative, Mapping):
            continue
        type_ref = str(alternative.get("type_ref") or "")
        if type_ref:
            refs.add(type_ref)
        value = alternative.get("value")
        if isinstance(value, Mapping):
            local_type = str(value.get("local_type") or "")
            semantic_family = str(value.get("semantic_family") or "")
            if local_type:
                refs.add(local_type)
            if semantic_family:
                refs.add("semantic-family:" + semantic_family)
    return tuple(sorted(refs))


def _mention_ref(factor: Mapping[str, Any]) -> str:
    metadata = factor.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("mention_ref"):
        return str(metadata["mention_ref"])
    for alternative in factor.get("alternatives") or ():
        if not isinstance(alternative, Mapping):
            continue
        value = alternative.get("value")
        if isinstance(value, Mapping) and value.get("mention_ref"):
            return str(value["mention_ref"])
    return ""


def _is_pronominal(type_refs: Sequence[str]) -> bool:
    return any(
        "pronoun" in ref.casefold() or "pronominal" in ref.casefold()
        for ref in type_refs
    )


def _is_entity_shaped(
    mention: Mapping[str, Any],
    type_refs: Sequence[str],
) -> bool:
    reason = str(mention.get("generation_reason") or "")
    if reason in {"named_entity_shape", "alias_hint"}:
        return True
    families = {
        ref.split(":", 1)[1]
        for ref in type_refs
        if ref.startswith("semantic-family:")
    }
    return bool(families.intersection(_ENTITY_FAMILIES))


def project_external_lookup_demands(
    artifacts: Mapping[str, Any],
    *,
    include_wiktionary: bool = True,
) -> tuple[ExternalLookupDemand, ...]:
    """Return nonblocking provider work for externally scoped open factors.

    The projection does not perform a lookup and cannot change the PNF graph.
    """

    mentions = _mention_rows(artifacts)
    factors = _factor_rows(artifacts)
    projected: list[ExternalLookupDemand] = []
    for demand in artifacts.get("resolution_demands") or ():
        if not isinstance(demand, Mapping):
            continue
        if str(demand.get("budget") or "") != "bounded_external_evidence":
            continue
        demand_ref = str(demand.get("demand_ref") or "")
        factor_ref = str(demand.get("factor_ref") or "")
        factor = factors.get(factor_ref)
        if not demand_ref or factor is None:
            continue
        mention_ref = _mention_ref(factor)
        mention = mentions.get(mention_ref)
        if mention is None:
            continue
        surface = str(mention.get("canonical_surface") or "").strip()
        if not surface:
            continue
        type_refs = _local_type_refs(factor)
        if _is_pronominal(type_refs):
            continue
        requested_facets = {
            str(value) for value in demand.get("requested_facets") or ()
        }
        if "external_identity_unresolved" in requested_facets and _is_entity_shaped(
            mention, type_refs
        ):
            projected.append(
                ExternalLookupDemand(
                    demand_ref=demand_ref,
                    subject_ref=factor_ref,
                    surface=surface,
                    demand_kind="entity_identity",
                    local_type_refs=type_refs,
                    priority=100,
                    provenance_refs=(mention_ref, EXTERNAL_LOOKUP_PROJECTION_REF),
                )
            )
            continue
        if not include_wiktionary:
            continue
        if requested_facets.intersection(
            {"local_type_unresolved", "external_identity_unresolved"}
        ) and surface.replace("-", "").isalpha():
            projected.append(
                ExternalLookupDemand(
                    demand_ref=demand_ref,
                    subject_ref=factor_ref,
                    surface=surface,
                    demand_kind="lexical_sense",
                    local_type_refs=type_refs,
                    priority=10,
                    provenance_refs=(mention_ref, EXTERNAL_LOOKUP_PROJECTION_REF),
                )
            )
    by_identity = {
        (row.demand_ref, row.demand_kind, row.lookup_key): row for row in projected
    }
    return tuple(
        sorted(
            by_identity.values(),
            key=lambda row: (-row.priority, row.demand_ref, row.demand_kind),
        )
    )


def summarize_external_lookup_plan(
    demands: Iterable[ExternalLookupDemand],
) -> dict[str, Any]:
    rows = tuple(demands)
    return {
        "projection_ref": EXTERNAL_LOOKUP_PROJECTION_REF,
        "demand_count": len(rows),
        "unique_lookup_key_count": len({row.lookup_key for row in rows}),
        "by_kind": {
            kind: sum(row.demand_kind == kind for row in rows)
            for kind in sorted({row.demand_kind for row in rows})
        },
        "authority": "planning_only",
        "network_performed": False,
    }


__all__ = [
    "EXTERNAL_LOOKUP_PROJECTION_REF",
    "project_external_lookup_demands",
    "summarize_external_lookup_plan",
]
