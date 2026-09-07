from __future__ import annotations

import pytest

from src.policy.external_graph_bridge import build_graph_view
from src.policy.wikibase_zelph_item_surface import (
    build_wikibase_zelph_item_surface,
    native_statement_rows_from_entity_export,
)


def _entity() -> dict[str, object]:
    return {
        "entities": {
            "QCOMPANY": {
                "id": "QCOMPANY",
                "lastrevid": 42,
                "claims": {
                    "P31": [
                        {
                            "id": "QCOMPANY$P31",
                            "rank": "normal",
                            "mainsnak": {
                                "snaktype": "value",
                                "datatype": "wikibase-item",
                                "datavalue": {"value": {"id": "Q783794"}},
                            },
                            "references": [{"hash": "ref-p31"}],
                        }
                    ],
                    "P5991": [
                        {
                            "id": "QCOMPANY$P5991",
                            "rank": "preferred",
                            "mainsnak": {
                                "snaktype": "value",
                                "datatype": "quantity",
                                "datavalue": {"value": {"amount": "+1100", "unit": "1"}},
                            },
                            "qualifiers": {
                                "P459": [
                                    {
                                        "snaktype": "value",
                                        "datatype": "wikibase-item",
                                        "datavalue": {"value": {"id": "Q56296245"}},
                                    }
                                ],
                                "P585": [
                                    {
                                        "snaktype": "value",
                                        "datatype": "time",
                                        "datavalue": {"value": {"time": "+2026-01-01T00:00:00Z"}},
                                    }
                                ],
                            },
                            "references": [{"hash": "ref-ghg"}],
                        }
                    ],
                    "P999": [
                        {
                            "id": "QCOMPANY$P999-novalue",
                            "rank": "normal",
                            "mainsnak": {
                                "snaktype": "novalue",
                                "datatype": "string",
                            },
                        }
                    ],
                },
            }
        }
    }


def _graph_view() -> dict[str, object]:
    return build_graph_view(
        graph_view_id="graph:qcompany",
        artifact_id="zelph:wikidata-pruned",
        artifact_revision="2026-03-09",
        coverage_state="complete",
        selected_sections=["left", "right", "nameOfNode"],
        selected_chunks=[{"which": "left", "chunkIndex": 1, "sizeBytes": 10}],
        selected_bytes=10,
        coverage_policy={"profile": "nat-qcompany-module", "seed": "QCOMPANY"},
        completeness_receipt_ref="coverage:graph:qcompany",
    )


def test_native_statement_rows_preserve_snak_rank_qualifiers_and_references() -> None:
    rows = native_statement_rows_from_entity_export(
        _entity(), subject_qid="QCOMPANY", entity_revision_ref="42"
    )
    by_ref = {row["statement_ref"]: row for row in rows}
    ghg = by_ref["QCOMPANY$P5991"]
    assert ghg["rank"] == "preferred"
    assert ghg["snak_type"] == "value"
    assert ghg["qualifiers"] == [
        {"property_id": "P459", "value": "Q56296245"},
        {"property_id": "P585", "value": "+2026-01-01T00:00:00Z"},
    ]
    assert ghg["reference_refs"] == ["ref-ghg"]
    assert by_ref["QCOMPANY$P999-novalue"]["snak_type"] == "novalue"


def test_graph_revision_difference_requires_alignment_receipt() -> None:
    with pytest.raises(ValueError, match="revision_alignment_ref"):
        build_wikibase_zelph_item_surface(
            entity_document=_entity(),
            subject_qid="QCOMPANY",
            entity_revision_ref="42",
            graph_view=_graph_view(),
            coverage_policy_ref="coverage:nat-item-v1",
            required_property_ids=["P31", "P5991", "P14143"],
        )


def test_complete_graph_does_not_auto_certify_native_property_families() -> None:
    joined = build_wikibase_zelph_item_surface(
        entity_document=_entity(),
        subject_qid="QCOMPANY",
        entity_revision_ref="42",
        graph_view=_graph_view(),
        coverage_policy_ref="coverage:nat-item-v1",
        required_property_ids=["P31", "P5991", "P14143"],
        revision_alignment_ref="align:entity42-to-graph-20260309",
    )
    surface = joined["item_surface"]
    assert surface["coverage_state"] == "uninspected"
    assert surface["property_inventory"]["coverage_by_property"] == {
        "P14143": "uninspected",
        "P31": "uninspected",
        "P5991": "uninspected",
        "P999": "uninspected",
    }
    assert surface["property_inventory"]["unresolved_required_property_ids"] == [
        "P14143",
        "P31",
        "P5991",
    ]


def test_explicit_qp_coverage_can_observe_no_statement_without_creating_novalue() -> None:
    joined = build_wikibase_zelph_item_surface(
        entity_document=_entity(),
        subject_qid="QCOMPANY",
        entity_revision_ref="42",
        graph_view=_graph_view(),
        coverage_policy_ref="coverage:nat-item-v1",
        required_property_ids=["P31", "P5991", "P14143"],
        property_coverage={
            "P31": "observed",
            "P5991": "observed",
            "P14143": "observed",
        },
        derived_relations=[{"property_id": "P279", "object_ref": "Q4830453"}],
        qualifier_specs={"P5991": {"allowed": ["P459", "P585"], "mandatory": ["P459"]}},
        scope_specs={
            "P31": {"as_main": True, "as_qualifier": False},
            "P5991": {"as_main": True, "as_qualifier": False},
            "P459": {"as_main": True, "as_qualifier": True},
            "P585": {"as_main": True, "as_qualifier": True},
        },
        revision_alignment_ref="align:entity42-to-graph-20260309",
    )
    surface = joined["item_surface"]
    inventory = surface["property_inventory"]
    assert inventory["no_statement_observed_property_ids"] == ["P14143"]
    assert "P14143" not in inventory["explicit_novalue_property_ids"]
    assert inventory["explicit_novalue_property_ids"] == ["P999"]
    assert any(
        row["feature"] == "property_relation"
        and row["condition"] == "P279->Q4830453"
        and row["value"] == "derived"
        for row in surface["peer_features"]
    )
    assert joined["authority"] == "diagnostic_only"
    assert joined["promotion_effect"] == "not_evaluated"
    assert joined["edit_effect"] == "none"
