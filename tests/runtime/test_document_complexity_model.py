from __future__ import annotations

import pytest

from src.runtime.document_complexity_model import (
    BatchComplexitySample,
    ComplexityTarget,
    batch_trend_receipt,
    hierarchy_depth,
    hierarchy_node_count,
    repeated_prefix_work,
    stage_complexity_contract,
)


def test_projection_contract_names_repeated_prefix_antipattern() -> None:
    contract = stage_complexity_contract("parser_observation_projection")

    assert contract.target is ComplexityTarget.SPARSE_GRAPH_LINEAR
    assert "tokens + atoms" in contract.target_bound
    assert "every prior atom" in contract.accidental_antipattern


def test_hierarchy_contract_accounts_for_interfaces_not_descendant_flattening() -> None:
    contract = stage_complexity_contract("hierarchical_graph_reduction")

    assert contract.target is ComplexityTarget.INTERFACE_SENSITIVE
    assert "sum_interfaces" in contract.target_bound
    assert "flatten" in contract.accidental_antipattern
    assert "descendant_bytes_reconstructed" in contract.work_variables


def test_exact_partial_four_ary_tree_count() -> None:
    assert hierarchy_node_count(16, 4) == 21
    assert hierarchy_depth(16, 4) == 2
    assert hierarchy_node_count(5, 4) == 8
    assert hierarchy_depth(5, 4) == 2


def test_repeated_prefix_work_is_quadratic_in_leaf_count() -> None:
    leaf_capacity = 4096

    four_leaves = repeated_prefix_work(4 * leaf_capacity, leaf_capacity)
    eight_leaves = repeated_prefix_work(8 * leaf_capacity, leaf_capacity)

    assert four_leaves == leaf_capacity * 10
    assert eight_leaves == leaf_capacity * 36
    assert eight_leaves / four_leaves == pytest.approx(3.6)


def test_consecutive_batch_receipt_detects_observed_projection_slowdown() -> None:
    durations_seconds = (49, 52, 62, 60, 63, 68, 70, 75, 80, 84, 86)
    completed = 49_152
    elapsed_ms = 0
    samples = [BatchComplexitySample(completed_units=completed, elapsed_ms=elapsed_ms)]
    for duration in durations_seconds:
        completed += 4096
        elapsed_ms += duration * 1000
        samples.append(
            BatchComplexitySample(
                completed_units=completed,
                elapsed_ms=elapsed_ms,
                lookup_operations=completed,
            )
        )

    receipt = batch_trend_receipt(samples)

    assert receipt.comparable_intervals is True
    assert receipt.first_rate == pytest.approx(83.5918, rel=1e-4)
    assert receipt.latest_rate == pytest.approx(47.6279, rel=1e-4)
    assert receipt.slowdown_fraction == pytest.approx(0.4302, rel=1e-3)
    assert all(row.units == 4096 for row in receipt.intervals)
    assert all(row.lookup_operations_delta == 4096 for row in receipt.intervals[1:])


def test_nonconsecutive_or_stalled_samples_are_not_treated_as_intervals() -> None:
    receipt = batch_trend_receipt(
        (
            BatchComplexitySample(completed_units=4096, elapsed_ms=10_000),
            BatchComplexitySample(completed_units=4096, elapsed_ms=20_000),
            BatchComplexitySample(completed_units=8192, elapsed_ms=20_000),
        )
    )

    assert receipt.intervals == ()
    assert receipt.comparable_intervals is False
    assert receipt.slowdown_fraction is None
