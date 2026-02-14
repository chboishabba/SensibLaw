from __future__ import annotations

import pytest


def _obs(**kw):
    from src.official_behavior.model import AlignmentObservation

    return AlignmentObservation(**kw)


def test_official_alignment_aggregation_requires_slice_declaration() -> None:
    from src.official_behavior.stats import SliceDeclarationError, aggregate_alignment_counts

    rows = [
        _obs(
            link_id="l1",
            action_id="a1",
            jurisdiction_id="us",
            institution_id="house",
            institution_kind="legislature_house",
            action_date="2001-01-01",
            alignment="aligned",
        )
    ]
    with pytest.raises(SliceDeclarationError):
        aggregate_alignment_counts(rows, group_by=("jurisdiction_id", "institution_id", "institution_kind"), slice=None)


def test_official_alignment_aggregation_disables_individuals_by_default() -> None:
    from src.official_behavior.stats import IndividualStatsDisabledError, aggregate_alignment_counts

    rows = [
        _obs(
            link_id="l1",
            action_id="a1",
            jurisdiction_id="us",
            institution_id="house",
            institution_kind="legislature_house",
            action_date="2001-01-01",
            alignment="aligned",
            official_id="o:1",
        )
    ]
    slice_decl = {"filters": {}, "time_bounds_declared": {"start": None, "end": None}, "group_by": ["official_id"]}
    with pytest.raises(IndividualStatsDisabledError):
        aggregate_alignment_counts(rows, group_by=("official_id",), allow_individuals=False, slice=slice_decl)


def test_official_alignment_aggregation_is_deterministic() -> None:
    from src.official_behavior.stats import aggregate_alignment_counts

    rows_a = [
        _obs(
            link_id="l1",
            action_id="a1",
            jurisdiction_id="us",
            institution_id="house",
            institution_kind="legislature_house",
            action_date="2001-01-01",
            alignment="misaligned",
        ),
        _obs(
            link_id="l2",
            action_id="a1",
            jurisdiction_id="us",
            institution_id="house",
            institution_kind="legislature_house",
            action_date="2001-01-01",
            alignment="aligned",
        ),
    ]
    rows_b = list(reversed(rows_a))
    slice_decl = {
        "filters": {"policy_area_id": "x"},
        "time_bounds_declared": {"start": "2001-01-01", "end": "2001-12-31"},
        "group_by": ["jurisdiction_id", "institution_id", "institution_kind"],
    }
    out_a = aggregate_alignment_counts(rows_a, group_by=("jurisdiction_id", "institution_id", "institution_kind"), slice=slice_decl)
    out_b = aggregate_alignment_counts(rows_b, group_by=("jurisdiction_id", "institution_id", "institution_kind"), slice=slice_decl)
    assert out_a == out_b
    assert out_a["mode"] == "descriptive_only"
    assert "interpretation_guard" in out_a
    assert out_a["corpus"]["n_total"] == 2


def test_official_beta_binomial_requires_slice_declaration() -> None:
    from src.official_behavior.stats import SliceDeclarationError, aggregate_alignment_beta_binomial

    rows = [
        _obs(
            link_id="l1",
            action_id="a1",
            jurisdiction_id="us",
            institution_id="house",
            institution_kind="legislature_house",
            action_date="2001-01-01",
            alignment="misaligned",
        )
    ]
    with pytest.raises(SliceDeclarationError):
        aggregate_alignment_beta_binomial(rows, slice=None)

