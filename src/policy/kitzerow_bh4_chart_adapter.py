"""Kitzerow BH4 chart → existing provider-neutral external-graph world model.

This is a thin *lane adapter*. It adds NO ontology compiler, new graph
authority, source ingest, review database or public editing capability.
Kitzerow's displayed Jan-2024 chart (ResearchGate 377218425) contains Rhea
identifiers. The complete proprietary original network and its exact PDF
revision remain unverified. All external identity matches are review-only.

Source: Kimberly Kitzerow, "BH4/Folate/Cobalamin/Homocysteine Pathway",
ResearchGate publication 377218425 (declared January 2024; page reports
full-text upload 2025-08-08), CC BY-NC-ND 4.0.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from src.policy.external_graph_bridge import (
    build_external_bridge_candidate,
    build_external_pressure_result,
    build_graph_view,
)
from src.policy.world_model import build_state_node, build_world_model
from src.policy.world_model_projections import project_review_surface
from src.policy.linkage_adapters import (
    build_external_bridge_adapter_fragment,
    build_claim_adapter_fragment,
    build_review_adapter_fragment,
    build_source_adapter_fragment,
    build_tranche_adapter_fragment,
    merge_linkage_fragments,
)

SCHEMA = "dashi.kitzerow-primary-chart-rhea-index.v1"
MATRIX_SCHEMA = "dashi.bh4-stoichiometric-matrix.v1"
RHEA_ID = re.compile(r"RHEA:[0-9]+")
SOURCE_REF = "https://www.researchgate.net/publication/377218425_BH4FolateCobalaminHomocysteine_Pathway"


def build_world(chart: Mapping[str, Any], matrix: Mapping[str, Any]) -> dict[str, Any]:
    """Use the generic graph/PNF carriers and retain bounded review residuals."""
    if chart.get("schema") != SCHEMA or matrix.get("schema") != MATRIX_SCHEMA:
        raise ValueError("source or matrix ABI mismatch")
    if chart.get("creator") != "Kimberly Kitzerow" or chart.get("publication_page") != SOURCE_REF:
        raise ValueError("creator/source identity not pinned")
    if chart.get("whole_proprietary_network_reconstructed") is not False:
        raise ValueError("unearned complete-author-network declaration")
    if chart.get("primary_claims_paid_by_source_index") is not False:
        raise ValueError("citation-only source index cannot pay original causal claims")
    if chart.get("same_compartment_flux_paid") is not False:
        raise ValueError("cross-reference cannot pay physiology")
    observed = chart.get("rhea_identifiers")
    if not isinstance(observed, list) or not observed:
        raise ValueError("no source-observed reaction IDs")
    chart_ids = []
    for r in observed:
        rid = r.get("rhea_id")
        if not isinstance(rid, str) or not RHEA_ID.fullmatch(rid):
            raise ValueError("bad chart reaction identity")
        if not isinstance(r.get("web_text_line"), int) or r["web_text_line"] <= 0:
            raise ValueError("missing source-local HTML text locator")
        chart_ids.append(rid)
    if len(chart_ids) != len(set(chart_ids)):
        raise ValueError("duplicate source-ID observations")
    panel_ids = matrix.get("reaction_index")
    if not isinstance(panel_ids, list) or len(panel_ids) != len(set(panel_ids)):
        raise ValueError("invalid finite-panel identifiers")
    if any(not isinstance(rid, str) or not RHEA_ID.fullmatch(rid) for rid in panel_ids):
        raise ValueError("invalid Rhea identity in matrix")

    chart_set = set(chart_ids)
    panel_set = set(panel_ids)
    overlap = sorted(chart_set & panel_set)
    chart_only = sorted(chart_set - panel_set)
    panel_only = sorted(panel_set - chart_set)

    # A chart text excerpt is not a complete snapshot of the diagram, and the
    # 12-reaction panel is not the declared boundary of Kitzerow's full map.
    graph = build_graph_view(
        graph_view_id="rhea:kitzerow:chart-observed-2026-11-02",
        artifact_id="researchgate:377218425:displayed-text",
        artifact_revision="page-upload-2025-08-08;pdf-binary-sha-unverified",
        coverage_state="incomplete",
        coverage_policy={"source": "publisher-displayed-text", "completeness": "bounded"},
        unresolved_coverage=[
            {"kind": "original_pdf_unverified", "scope": "page/diagram geometry and binary revision"},
            {"kind": "author_network_incomplete", "scope": "full proprietary BioGene network"},
            {"kind": "physical_context_unpaid", "scope": "tissue, isoform, compartment and flux"}
        ],
        source={"creator": "Kimberly Kitzerow", "publication_page": SOURCE_REF,
                "declared_month": chart["declared_publication_month"],
                "observed_upload_date": chart["observed_full_text_upload_date"]},
    )
    nodes = []
    links = []
    pressure = []
    fragments = []
    source_id = "kitzerow:chart:377218425"
    for row in sorted(observed, key=lambda r: r["rhea_id"]):
        rid = row["rhea_id"]
        local = "kitzerow:chart-reaction:" + rid
        evidence = f"{SOURCE_REF}#L{row['web_text_line']}"
        nodes.append(build_state_node(
            node_id=local, node_kind="creator-chart-reaction-mention",
            label=rid, status="candidate", source_anchor_ids=[source_id],
            metadata={"source_locator": evidence,
                      "owner": "Kimberly Kitzerow", "observed_identifier": rid,
                      "same_biological_event_verified": False}))
        links.append(build_external_bridge_candidate(
            bridge_candidate_id="kitzerow:rhea:bridge:" + rid,
            subject_ref=local, subject_kind="concept",
            bridge_namespace="rhea", external_ref=rid,
            attachment_kind="related_concept", graph_view_ref=graph["graph_view_id"],
            basis=[{"source_anchor_id": source_id, "source_locator": evidence,
                    "basis": "literal Rhea ID in displayed creator chart"}],
            external_revision_ref=graph["artifact_revision"],
            candidate_status="review_required",
            adapter_id="kitzerow-rhea-observed-chart"))
        pressure.append(build_external_pressure_result(
            pressure_result_id="kitzerow:chart-vs-panel:" + rid,
            target_ref=local, graph_view_ref=graph["graph_view_id"],
            profile_id="finite-Rhea-panel-coverage-only", outcome="abstain",
            diagnostics=[{"kind": "identifier-overlap",
                          "panel_contains_id": rid in panel_set}],
            residuals=[{"kind": "physiology-unpaid",
                        "reason": "literal ID match does not prove same compartment, causal role or rate"}]))
        fragments.extend([
            build_source_adapter_fragment(
                anchor_id=source_id, label="Kitzerow public chart",
                metadata={"creator": "Kimberly Kitzerow",
                          "revision": graph["artifact_revision"]},
                target_id=local),
            build_claim_adapter_fragment(
                node_id=local, label=rid, source_id=source_id,
                metadata={"source_locator": evidence,
                          "authority": "candidate-only"}),
            build_external_bridge_adapter_fragment(
                node_id="rhea:external-candidate:" + rid,
                label="Rhea external identity candidate",
                metadata={"bridge": "kitzerow:rhea:bridge:" + rid},
                upstream_node_ids=[local])
        ])
    review_id = "kitzerow:bh4:review"
    tranche_id = "kitzerow:bh4:review-tranche"
    fragments.append(build_review_adapter_fragment(
        node_id=review_id, label="Kitzerow original/curated comparison",
        upstream_node_ids=["rhea:external-candidate:" + r for r in sorted(chart_set)]))
    fragments.append(build_tranche_adapter_fragment(
        node_id=tranche_id, label="Kitzerow BH4 review only", upstream_node_ids=[review_id]))
    linkage = merge_linkage_fragments(*fragments)
    model = build_world_model(
        model_id="kitzerow-bh4:source-observed-chart",
        lane_family="biology-source-ontology-bridge",
        model_status="candidate",
        source_mode="source-observed-chart",
        entities=nodes,
        external_graph_views=[graph],
        external_bridge_candidates=links,
        external_pressure_results=pressure,
        provenance_graph=[{"source_id": source_id, "source_uri": SOURCE_REF,
                           "publication_month": chart["declared_publication_month"],
                           "observed_upload_date": chart["observed_full_text_upload_date"],
                           "original_pdf_binary_verified": False,
                           "license": chart["license_declared"]}],
        residuals=[{"kind": "creator-network-coverage-unknown"},
                   {"kind": "external-event-identity-unpaid"},
                   {"kind": "context-matched-flux-unpaid"}],
        summary={"source_observed_chart_ids": len(chart_ids),
                 "finite_panel_ids": len(panel_ids),
                 "identifier_overlap": overlap,
                 "chart_observed_only": chart_only,
                 "finite_panel_only": panel_only,
                 "denominator_for_whole_creator_network": None},
        metadata={"read_only": True, "external_identifiers_are_advisory": True,
                  "live_ontology_writes": False, "same_object_proved": False,
                  "causal_theory_verified": False},
    )
    return {"world_model": model,
            "review_projection": project_review_surface(model),
            "linkage_fragment": linkage,
            "author_chart_license": chart["license_declared"],
            "source_authority": "creator-authored observed chart",
            "external_database_authority": "Rhea independently curated",
            "implementation_owner": "SensibLaw thin generic-world-model adapter",
            "status": "source-written; no source binary or runtime certification"}


__all__ = ["build_world"]
