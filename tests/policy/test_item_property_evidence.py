from __future__ import annotations

from src.policy.item_property_evidence import build_item_property_evidence_surface


def _surface() -> dict[str, object]:
    return build_item_property_evidence_surface(
        subject_qid="QCOMPANY",
        source_revision_ref="wikidata:QCOMPANY@42",
        coverage_state="observed",
        coverage_policy_ref="coverage:nat-item-neighbourhood-v1",
        statements=[
            {
                "statement_ref": "QCOMPANY$P31",
                "property_id": "P31",
                "value": "Q783794",
                "value_ref": "Q783794",
                "value_kind": "item",
                "rank": "normal",
            },
            {
                "statement_ref": "QCOMPANY$P5991-normal",
                "property_id": "P5991",
                "value": "1000",
                "value_kind": "quantity",
                "rank": "normal",
                "qualifiers": {"P459": ["Q56296245"], "P585": ["2025"]},
            },
            {
                "statement_ref": "QCOMPANY$P5991-preferred",
                "property_id": "P5991",
                "value": "1100",
                "value_kind": "quantity",
                "rank": "preferred",
                "qualifiers": {"P459": ["Q56296245"], "P585": ["2026"]},
            },
            {
                "statement_ref": "QCOMPANY$P5991-deprecated",
                "property_id": "P5991",
                "value": "900",
                "value_kind": "quantity",
                "rank": "deprecated",
            },
        ],
        qualifier_specs={
            "P5991": {"allowed": ["P459", "P585"], "mandatory": ["P459"]},
        },
        scope_specs={
            "P31": {"as_main": True, "as_qualifier": False},
            "P5991": {"as_main": True, "as_qualifier": False},
            "P459": {"as_main": True, "as_qualifier": True},
            "P585": {"as_main": True, "as_qualifier": True},
        },
        derived_relations=[
            {"property_id": "P31", "object_ref": "Q783794"},
            {"property_id": "P279", "object_ref": "Q4830453"},
        ],
    )


def test_actual_item_properties_are_preserved_as_inventory() -> None:
    surface = _surface()
    assert surface["property_inventory"]["observed_property_ids"] == ["P31", "P5991"]
    assert surface["property_inventory"]["truthy_property_ids"] == ["P31", "P5991"]
    assert surface["property_inventory"]["statement_count"] == 4


def test_rank_and_truthy_visibility_are_separate_coordinates() -> None:
    statements = {row["statement_ref"]: row for row in _surface()["statements"]}
    preferred = statements["QCOMPANY$P5991-preferred"]
    normal = statements["QCOMPANY$P5991-normal"]
    deprecated = statements["QCOMPANY$P5991-deprecated"]

    assert preferred["rank"] == "preferred"
    assert preferred["statement_visibility"] == "truthy"
    assert preferred["truthy"] is True

    assert normal["rank"] == "normal"
    assert normal["statement_visibility"] == "non_truthy"
    assert normal["truthy"] is False

    assert deprecated["rank"] == "deprecated"
    assert deprecated["statement_visibility"] == "non_truthy"
    assert deprecated["truthy"] is False

    features = {
        (row["feature"], row["condition"], row["value"])
        for row in _surface()["peer_features"]
    }
    assert ("statement_rank", "P5991|QCOMPANY$P5991-preferred", "preferred") in features
    assert ("statement_visibility", "P5991|QCOMPANY$P5991-preferred", "truthy") in features
    assert ("statement_rank", "P5991|QCOMPANY$P5991-normal", "normal") in features
    assert ("statement_visibility", "P5991|QCOMPANY$P5991-normal", "non_truthy") in features


def test_qualifier_and_scope_receipts_remain_statement_conditioned() -> None:
    surface = _surface()
    preferred = next(
        row for row in surface["statements"] if row["statement_ref"] == "QCOMPANY$P5991-preferred"
    )
    assert preferred["qualifier_constraint"] == "valid"
    assert preferred["main_property_scope"] == "valid"
    assert preferred["qualifier_property_scopes"] == [
        {"property_id": "P459", "state": "valid"},
        {"property_id": "P585", "state": "valid"},
    ]


def test_asserted_and_derived_property_relations_do_not_collapse() -> None:
    surface = _surface()
    relation_features = {
        (row["condition"], row["value"])
        for row in surface["peer_features"]
        if row["feature"] == "property_relation"
    }
    assert ("P31->Q783794", "asserted") in relation_features
    assert ("P279->Q4830453", "derived") in relation_features


def test_unprofiled_property_constraint_is_uninspected_not_valid() -> None:
    surface = build_item_property_evidence_surface(
        subject_qid="QX",
        source_revision_ref="wikidata:QX@1",
        coverage_state="observed",
        coverage_policy_ref="coverage:test",
        statements=[
            {
                "statement_ref": "QX$P999",
                "property_id": "P999",
                "value": "x",
                "rank": "normal",
                "qualifiers": {"P888": ["y"]},
            }
        ],
    )
    statement = surface["statements"][0]
    assert statement["qualifier_constraint"] == "uninspected"
    assert statement["main_property_scope"] == "uninspected"
    assert statement["qualifier_property_scopes"] == [
        {"property_id": "P888", "state": "uninspected"}
    ]
