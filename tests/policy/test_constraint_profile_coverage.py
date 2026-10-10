from __future__ import annotations

from src.policy.item_property_evidence import build_item_property_evidence_surface


def _statement() -> list[dict[str, object]]:
    return [
        {
            "statement_ref": "QX$P17",
            "property_id": "P17",
            "snak_type": "value",
            "value": "Q183",
            "value_ref": "Q183",
            "value_kind": "wikibase-item",
            "rank": "normal",
        }
    ]


def test_absent_profile_is_uninspected_when_constraint_table_not_covered() -> None:
    surface = build_item_property_evidence_surface(
        subject_qid="QX",
        source_revision_ref="1",
        statements=_statement(),
        coverage_state="observed",
        coverage_policy_ref="coverage:test",
        property_coverage={"P17": "observed"},
        qualifier_specs={},
        qualifier_profile_coverage_state="uninspected",
        scope_specs={},
        scope_profile_coverage_state="uninspected",
    )
    statement = surface["statements"][0]
    assert statement["qualifier_constraint"] == "uninspected"
    assert statement["main_property_scope"] == "uninspected"


def test_absent_profile_is_unconstrained_when_constraint_table_is_covered() -> None:
    surface = build_item_property_evidence_surface(
        subject_qid="QX",
        source_revision_ref="1",
        statements=_statement(),
        coverage_state="observed",
        coverage_policy_ref="coverage:test",
        property_coverage={"P17": "observed"},
        qualifier_specs={},
        qualifier_profile_coverage_state="observed",
        scope_specs={},
        scope_profile_coverage_state="observed",
    )
    statement = surface["statements"][0]
    assert statement["qualifier_constraint"] == "unconstrained"
    assert statement["main_property_scope"] == "unconstrained"
    assert surface["constraint_profile_coverage"] == {
        "qualifier": "observed",
        "scope": "observed",
    }
    features = {
        (row["feature"], row["condition"], row["value"])
        for row in surface["peer_features"]
    }
    assert ("qualifier_profile_coverage", "constraint_table", "observed") in features
    assert ("scope_profile_coverage", "constraint_table", "observed") in features
