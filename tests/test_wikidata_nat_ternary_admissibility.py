from __future__ import annotations

import pytest

from src.ontology.wikidata_nat_ternary_admissibility import (
    BASE369_NINE_AXIS_ORDER,
    build_nat_ternary_admissibility_projection,
    decode_snak_trit,
    encode_snak_type,
)


@pytest.mark.parametrize("snak_type", ["novalue", "somevalue", "value"])
def test_epistemic_centred_snak_codec_round_trips(snak_type: str) -> None:
    trit = encode_snak_type(snak_type)
    assert trit in {-1, 0, 1}
    assert decode_snak_trit(trit) == snak_type


@pytest.mark.parametrize("snak_type", ["novalue", "somevalue", "value"])
def test_absence_centred_snak_codec_round_trips(snak_type: str) -> None:
    trit = encode_snak_type(snak_type, orientation="absence_centred")
    assert trit in {-1, 0, 1}
    assert decode_snak_trit(trit, orientation="absence_centred") == snak_type


def test_epistemic_centred_orientation_is_minus_zero_plus() -> None:
    assert encode_snak_type("novalue") == -1
    assert encode_snak_type("somevalue") == 0
    assert encode_snak_type("value") == 1


def test_absence_centred_orientation_puts_literal_absence_at_zero() -> None:
    assert encode_snak_type("novalue", orientation="absence_centred") == 0
    assert encode_snak_type("somevalue", orientation="absence_centred") == -1
    assert encode_snak_type("value", orientation="absence_centred") == 1


def test_live_residuals_are_open_zero_not_boolean_false() -> None:
    recomputation = {
        "recomputation_ref": "recompute:1",
        "execution_outcome": "executed_with_output",
        "qid_identity_resolved": True,
        "coverage_coordinate_paid": True,
        "rank_visibility_evaluated": False,
        "qualifier_constraints_evaluated": False,
        "property_scope_evaluated": False,
        "property_engine_derivability_evaluated": False,
        "source_support_paid": False,
        "observed_native_snak_types": ["value", "somevalue", "novalue"],
    }
    projection = build_nat_ternary_admissibility_projection(recomputation)

    assert projection["dimension"] == 10
    assert projection["axis_trits"]["subject_identity"] == 1
    assert projection["axis_trits"]["transport"] == 1
    assert projection["axis_trits"]["native_family_coverage"] == 1
    assert projection["axis_trits"]["rank_visibility"] == 0
    assert projection["axis_trits"]["qualifier_constraints"] == 0
    assert projection["axis_trits"]["property_scope"] == 0
    assert projection["axis_trits"]["property_derivability"] == 0
    assert projection["axis_trits"]["source_support"] == 0
    assert projection["axis_trits"]["authority"] == 0
    assert projection["axis_trits"]["semantic_correspondence"] == 0
    assert projection["binary_zero_means_semantic_false"] is False


def test_nine_axis_projection_is_exact_base369_shape_without_monster_promotion() -> None:
    recomputation = {
        "recomputation_ref": "recompute:2",
        "execution_outcome": "executed_with_output",
        "qid_identity_resolved": True,
        "coverage_coordinate_paid": True,
        "rank_visibility_evaluated": False,
        "qualifier_constraints_evaluated": False,
        "property_scope_evaluated": False,
        "property_engine_derivability_evaluated": False,
        "source_support_paid": False,
        "observed_native_snak_types": ["novalue"],
    }
    projection = build_nat_ternary_admissibility_projection(recomputation)

    assert tuple(projection["base369_nine_axis_order"]) == BASE369_NINE_AXIS_ORDER
    assert len(projection["base369_nine_trits"]) == 9
    assert set(projection["base369_nine_trits"]) <= {-1, 0, 1}
    assert projection["base369_nominal_state_count"] == 19683
    assert projection["same_carrier_implies_monster_action"] is False
    assert projection["snak_semantics_are_truth_values"] is False


def test_snak_encodings_are_representation_views_not_admissibility_states() -> None:
    recomputation = {
        "recomputation_ref": "recompute:3",
        "execution_outcome": "executed_with_output",
        "qid_identity_resolved": True,
        "coverage_coordinate_paid": True,
        "observed_native_snak_types": ["novalue", "somevalue", "value"],
    }
    projection = build_nat_ternary_admissibility_projection(recomputation)

    assert projection["epistemic_centred_snak_trits"] == [-1, 0, 1]
    assert projection["absence_centred_snak_trits"] == [0, -1, 1]
    assert projection["unbalanced_snak_digits"] == [1, 2, 3]
