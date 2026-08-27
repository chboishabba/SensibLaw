from __future__ import annotations

from src.storage.postgres.delta_projection_certification import (
    DeltaCertificationLayer,
    certify_layers,
    compare_multiset,
)


def test_compare_multiset_preserves_multiplicity_and_ignores_input_order() -> None:
    left = ((1, b"a"), (2, b"b"), (1, b"a"))
    right = ((2, b"b"), (1, b"a"), (1, b"a"))
    result = compare_multiset(left, right)
    assert result["equal"] is True
    assert result["legacy_count"] == 3
    assert result["legacy_sha256"] == result["projected_sha256"]


def test_compare_multiset_reports_missing_multiplicity() -> None:
    result = compare_multiset(((1,), (1,)), ((1,),))
    assert result["equal"] is False
    assert result["missing_count"] == 1
    assert result["extra_count"] == 0


def test_certify_layers_exposes_commuting_square_failure() -> None:
    layers = (
        DeltaCertificationLayer("source_delta", ("source",)),
        DeltaCertificationLayer("authority", ("authority",)),
    )
    result = certify_layers(
        {"source": ((1,),), "authority": ((2,),)},
        {"source": ((1,),), "authority": ((3,),)},
        layers=layers,
    )
    assert result["commuting_square_equal"] is False
    assert result["layers"]["source_delta"]["equal"] is True
    assert result["layers"]["authority"]["equal"] is False
    assert result["mismatch_layers"] == ["authority"]
