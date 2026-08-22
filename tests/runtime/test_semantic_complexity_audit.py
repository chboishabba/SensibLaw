from __future__ import annotations

from fractions import Fraction

import pytest

from src.runtime.semantic_complexity_audit import (
    ConsumerSufficientCompression,
    FrontierWorkCertificate,
    OperationalCarrierCost,
    repeated_full_fibre_exposure,
)


def test_consumer_safe_projection_must_preserve_residual_and_provenance() -> None:
    source = OperationalCarrierCost(nodes=100, edges=80, residuals=12, encoded_units=20)
    projected = OperationalCarrierCost(nodes=10, edges=8, residuals=12, encoded_units=5)

    verified = ConsumerSufficientCompression(
        source,
        projected,
        consumer_factorizes=True,
        residuals_preserved=True,
        provenance_preserved=True,
    )
    destructive = ConsumerSufficientCompression(
        source,
        projected,
        consumer_factorizes=True,
        residuals_preserved=False,
        provenance_preserved=True,
    )
    unknown = ConsumerSufficientCompression(
        source,
        projected,
        consumer_factorizes=None,
        residuals_preserved=True,
        provenance_preserved=True,
    )

    assert verified.state == "verified"
    assert verified.saved_units == source.unit_cost - projected.unit_cost
    assert destructive.state == "violated"
    assert destructive.saved_units is None
    assert unknown.state == "indeterminate"


def test_projection_that_increases_operational_carrier_is_not_a_compression() -> None:
    result = ConsumerSufficientCompression(
        OperationalCarrierCost(nodes=2),
        OperationalCarrierCost(nodes=3),
        consumer_factorizes=True,
        residuals_preserved=True,
        provenance_preserved=True,
    )
    assert result.state == "violated"


def test_frontier_work_fails_closed_without_a_measured_work_count() -> None:
    assert FrontierWorkCertificate(5, 7, None, 100).state == "indeterminate"
    assert FrontierWorkCertificate(5, 7, 12, 100).state == "verified"
    assert FrontierWorkCertificate(5, 7, 13, 100).state == "violated"


def test_repeated_full_fibre_scan_exposes_triangular_work() -> None:
    exposure = repeated_full_fibre_exposure([1] * 8)

    assert exposure.final_fibre_size == 8
    assert exposure.repeated_full_fibre_units == 36
    assert exposure.append_only_units == 8
    assert exposure.avoidable_rescan_units == 28
    assert exposure.amplification == Fraction(9, 2)


def test_batched_waves_still_expose_only_physical_rescan_not_semantic_invalidity() -> None:
    exposure = repeated_full_fibre_exposure([100, 100, 100])

    assert exposure.final_fibre_size == 300
    assert exposure.repeated_full_fibre_units == 600
    assert exposure.amplification == Fraction(2, 1)


def test_negative_counts_are_rejected() -> None:
    with pytest.raises(ValueError):
        OperationalCarrierCost(nodes=-1)
    with pytest.raises(ValueError):
        repeated_full_fibre_exposure([1, -1])
