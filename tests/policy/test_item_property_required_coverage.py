from __future__ import annotations

from src.policy.item_property_evidence import build_item_property_evidence_surface


def test_required_property_observed_absent_is_distinct_from_uninspected() -> None:
    observed_absent = build_item_property_evidence_surface(
        subject_qid="QCOMPANY",
        source_revision_ref="wikidata:QCOMPANY@50",
        coverage_state="observed",
        coverage_policy_ref="coverage:nat-required-v1",
        required_property_ids=["P31", "P5991", "P14143"],
        property_coverage={
            "P31": "observed",
            "P5991": "observed",
            "P14143": "observed",
        },
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
                "statement_ref": "QCOMPANY$P5991",
                "property_id": "P5991",
                "value": "1000",
                "rank": "normal",
            },
        ],
    )
    inventory = observed_absent["property_inventory"]
    assert inventory["observed_absent_property_ids"] == ["P14143"]
    assert inventory["unresolved_required_property_ids"] == []
    assert {
        (row["feature"], row["condition"], row["value"])
        for row in observed_absent["peer_features"]
    } >= {("property_presence", "P14143", "absent")}

    uninspected = build_item_property_evidence_surface(
        subject_qid="QCOMPANY",
        source_revision_ref="wikidata:QCOMPANY@50",
        coverage_state="observed",
        coverage_policy_ref="coverage:nat-required-v1",
        required_property_ids=["P31", "P5991", "P14143"],
        property_coverage={
            "P31": "observed",
            "P5991": "observed",
            "P14143": "uninspected",
        },
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
                "statement_ref": "QCOMPANY$P5991",
                "property_id": "P5991",
                "value": "1000",
                "rank": "normal",
            },
        ],
    )
    inventory = uninspected["property_inventory"]
    assert inventory["observed_absent_property_ids"] == []
    assert inventory["unresolved_required_property_ids"] == ["P14143"]
    assert (
        "property_presence",
        "P14143",
        "absent",
    ) not in {
        (row["feature"], row["condition"], row["value"])
        for row in uninspected["peer_features"]
    }


def test_incomplete_property_family_cannot_make_normal_statement_truthy() -> None:
    surface = build_item_property_evidence_surface(
        subject_qid="QCOMPANY",
        source_revision_ref="wikidata:QCOMPANY@51",
        coverage_state="observed",
        coverage_policy_ref="coverage:nat-required-v1",
        required_property_ids=["P5991"],
        property_coverage={"P5991": "incomplete"},
        statements=[
            {
                "statement_ref": "QCOMPANY$P5991-normal",
                "property_id": "P5991",
                "value": "1000",
                "rank": "normal",
            }
        ],
    )
    statement = surface["statements"][0]
    assert statement["rank"] == "normal"
    assert statement["statement_visibility"] == "unresolved"
    assert statement["truthy"] is None
