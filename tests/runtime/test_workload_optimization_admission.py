from __future__ import annotations

from src.runtime.workload_optimization_admission import (
    BackendFamily,
    BackendMeasurement,
    OptimizationAdmissionReceipt,
    WorkloadShape,
)


def _measurement(
    family: BackendFamily,
    *,
    total_ns: int,
    authority_equal: bool = True,
    setup_ns: int = 0,
    repack_ns: int = 0,
    dispatch_ns: int = 0,
    transfer_ns: int = 0,
    kernel_ns: int | None = None,
) -> BackendMeasurement:
    boundary = setup_ns + repack_ns + dispatch_ns + transfer_ns
    if kernel_ns is None:
        kernel_ns = total_ns - boundary
    return BackendMeasurement(
        family=family,
        authority_equal=authority_equal,
        setup_ns=setup_ns,
        repack_ns=repack_ns,
        dispatch_ns=dispatch_ns,
        transfer_ns=transfer_ns,
        kernel_ns=kernel_ns,
        total_ns=total_ns,
    )


def test_python_swar_grocery_workload_is_rejected_even_with_exact_authority() -> None:
    workload = WorkloadShape(
        item_count=224_371,
        mean_fibre_items=22.4371,
        homogeneous=False,
        already_candidate_native=False,
        repacking_required=True,
        useful_operations=224_371 * 7,
    )
    scalar = _measurement(BackendFamily.PACKED_SCALAR, total_ns=355_120_122)
    swar = _measurement(
        BackendFamily.NATIVE_SWAR,
        total_ns=3_318_574_713,
        repack_ns=1_000_000_000,
    )

    receipt = OptimizationAdmissionReceipt(workload, scalar, swar)

    assert receipt.authority_exact
    assert not receipt.structurally_plausible
    assert receipt.end_to_end_improvement < 0
    assert not receipt.promoted
    assert receipt.reason == "workload-geometry-does-not-amortize-candidate-boundaries"


def test_fast_inner_kernel_does_not_hide_large_boundary_cost() -> None:
    workload = WorkloadShape(
        item_count=100_000,
        mean_fibre_items=20.0,
        homogeneous=True,
        already_candidate_native=False,
        repacking_required=True,
        useful_operations=1_000_000,
    )
    scalar = _measurement(BackendFamily.PACKED_SCALAR, total_ns=1_000)
    candidate = _measurement(
        BackendFamily.BATCH_VECTOR,
        total_ns=1_200,
        setup_ns=100,
        repack_ns=800,
        kernel_ns=300,
    )

    receipt = OptimizationAdmissionReceipt(workload, scalar, candidate)

    assert candidate.kernel_ns < scalar.kernel_ns
    assert receipt.structurally_plausible
    assert not receipt.promoted
    assert receipt.reason == "measured-end-to-end-improvement-below-gate"


def test_persistent_homogeneous_native_work_can_earn_promotion() -> None:
    workload = WorkloadShape(
        item_count=1_000_000,
        mean_fibre_items=1_000.0,
        homogeneous=True,
        already_candidate_native=True,
        repacking_required=False,
        useful_operations=100_000_000,
    )
    scalar = _measurement(BackendFamily.PACKED_SCALAR, total_ns=10_000)
    candidate = _measurement(
        BackendFamily.NATIVE_SWAR,
        total_ns=7_000,
        setup_ns=200,
        kernel_ns=6_800,
    )

    receipt = OptimizationAdmissionReceipt(workload, scalar, candidate)

    assert receipt.structurally_plausible
    assert receipt.end_to_end_improvement == 0.3
    assert receipt.promoted
    assert receipt.reason == "promoted"


def test_authority_mismatch_blocks_even_large_speedup() -> None:
    workload = WorkloadShape(
        item_count=1_000_000,
        mean_fibre_items=1_000.0,
        homogeneous=True,
        already_candidate_native=True,
        repacking_required=False,
        useful_operations=100_000_000,
    )
    scalar = _measurement(BackendFamily.PACKED_SCALAR, total_ns=10_000)
    candidate = _measurement(
        BackendFamily.ACCELERATOR,
        total_ns=1_000,
        authority_equal=False,
        transfer_ns=100,
        kernel_ns=900,
    )

    receipt = OptimizationAdmissionReceipt(workload, scalar, candidate)

    assert not receipt.authority_exact
    assert not receipt.promoted
    assert receipt.reason == "semantic-authority-mismatch"


def test_boundary_fraction_is_explicit_in_receipt() -> None:
    workload = WorkloadShape(
        item_count=100,
        mean_fibre_items=10.0,
        homogeneous=True,
        already_candidate_native=False,
        repacking_required=False,
        useful_operations=1_000,
    )
    scalar = _measurement(BackendFamily.PACKED_SCALAR, total_ns=1_000)
    candidate = _measurement(
        BackendFamily.BATCH_VECTOR,
        total_ns=800,
        setup_ns=50,
        dispatch_ns=50,
        transfer_ns=100,
        kernel_ns=600,
    )

    receipt = OptimizationAdmissionReceipt(workload, scalar, candidate)
    payload = receipt.as_dict()

    assert payload["candidate_boundary_fraction"] == 0.25
    assert payload["promoted"] is True
