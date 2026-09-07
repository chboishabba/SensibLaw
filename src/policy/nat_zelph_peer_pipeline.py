"""End-to-end Nat peer evidence pipeline over native Wikibase + routed Zelph.

This is the preferred orchestration seam for the current Nat climate lane:

    routed Zelph relation observations
      -> conservative P31/P279 type module
      -> native Wikibase + graph item surface
      -> governed peer-cohort residual
      -> least-privilege Nat pressure weld

Every stage remains diagnostic.  The pipeline does not infer P5991=P14143,
create migration safety, create policy authority, or execute an edit.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .nat_climate_peer_pressure import weld_nat_peer_cohort_residual
from .wikibase_zelph_item_surface import build_wikibase_zelph_item_surface
from .zelph_routed_relation_observations import (
    ZELPH_ROUTED_RELATION_OBSERVATIONS_SCHEMA_VERSION,
    type_relation_rows,
)
from .zelph_type_module import build_zelph_type_module

NAT_ZELPH_PEER_PIPELINE_SCHEMA_VERSION = "sl.nat_zelph_peer_pipeline.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _type_module_derived_relations(type_module: Mapping[str, Any]) -> list[dict[str, str]]:
    """Project module relations into the item surface without claiming assertion."""

    rows: list[dict[str, str]] = []
    for raw in type_module.get("relations") or ():
        if not isinstance(raw, Mapping):
            continue
        property_id = _text(raw.get("property_id"))
        object_ref = _text(raw.get("object_ref"))
        if property_id not in {"P31", "P279"} or not object_ref:
            continue
        rows.append(
            {
                "property_id": property_id,
                "object_ref": object_ref,
                "origin": "derived",
            }
        )
    rows.sort(key=lambda row: (row["property_id"], row["object_ref"]))
    return rows


def run_nat_zelph_peer_pipeline(
    *,
    pressure_assessment: Mapping[str, Any],
    invariant_snapshot: Mapping[str, Any],
    entity_document: Mapping[str, Any],
    subject_qid: str,
    entity_revision_ref: str,
    graph_view: Mapping[str, Any],
    routed_observations: Mapping[str, Any],
    type_preservation_receipt: Mapping[str, Any],
    type_module_receipt_ref: str,
    coverage_policy_ref: str,
    required_property_ids: Sequence[str],
    property_coverage: Mapping[str, Any] | None = None,
    qualifier_specs: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    qualifier_profile_coverage_state: str = "uninspected",
    scope_specs: Mapping[str, Mapping[str, Any]] | None = None,
    scope_profile_coverage_state: str = "uninspected",
    revision_alignment_ref: str | None = None,
    candidate_ref: str | None = None,
    type_query_family_ref: str = "query:p31-p279-type-closure",
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Compile the concrete Nat evidence path without widening authority."""

    qid = _text(subject_qid)
    if not qid:
        raise ValueError("subject_qid is required")
    if (
        _text(routed_observations.get("schema_version"))
        != ZELPH_ROUTED_RELATION_OBSERVATIONS_SCHEMA_VERSION
    ):
        raise ValueError("pipeline requires normalized routed Zelph observations")
    if _text(routed_observations.get("subject_qid")) != qid:
        raise ValueError("routed observation subject does not match native entity subject")
    if _text(routed_observations.get("query_family_ref")) != _text(type_query_family_ref):
        raise ValueError("routed observation query family does not match type query family")

    relation_rows = type_relation_rows(routed_observations)
    type_module = build_zelph_type_module(
        subject_qid=qid,
        graph_view=graph_view,
        relation_observations=relation_rows,
        preservation_receipt=type_preservation_receipt,
        query_family_ref=type_query_family_ref,
        module_receipt_ref=type_module_receipt_ref,
    )
    derived_relations = _type_module_derived_relations(type_module)

    joined = build_wikibase_zelph_item_surface(
        entity_document=entity_document,
        subject_qid=qid,
        entity_revision_ref=entity_revision_ref,
        graph_view=graph_view,
        coverage_policy_ref=coverage_policy_ref,
        required_property_ids=required_property_ids,
        property_coverage=property_coverage,
        derived_relations=derived_relations,
        derived_relation_query_family_ref=type_query_family_ref,
        query_preservation_receipt=type_preservation_receipt,
        qualifier_specs=qualifier_specs,
        qualifier_profile_coverage_state=qualifier_profile_coverage_state,
        scope_specs=scope_specs,
        scope_profile_coverage_state=scope_profile_coverage_state,
        revision_alignment_ref=revision_alignment_ref,
        evidence_refs=[
            *evidence_refs,
            _text(routed_observations.get("execution_receipt_ref")),
            _text(type_module.get("module_receipt_ref")),
        ],
    )
    item_surface = joined["item_surface"]

    welded = weld_nat_peer_cohort_residual(
        pressure_assessment=pressure_assessment,
        invariant_snapshot=invariant_snapshot,
        item_surface=item_surface,
        candidate_ref=candidate_ref,
        evidence_refs=[
            *evidence_refs,
            _text(joined.get("content_identity", {}).get("content_id")),
            _text(type_module.get("module_receipt_ref")),
        ],
    )

    return {
        "schema_version": NAT_ZELPH_PEER_PIPELINE_SCHEMA_VERSION,
        "subject_qid": qid,
        "routed_observations": deepcopy(dict(routed_observations)),
        "type_module": type_module,
        "joined_item_surface": joined,
        "pressure_assessment": welded,
        "authority": "diagnostic_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }


__all__ = [
    "NAT_ZELPH_PEER_PIPELINE_SCHEMA_VERSION",
    "run_nat_zelph_peer_pipeline",
]
