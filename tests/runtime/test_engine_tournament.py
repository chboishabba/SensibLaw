from __future__ import annotations

from src.runtime.engine_tournament import (
    EngineKernel,
    EngineTournamentReceipt,
    KernelGeometry,
    KernelOutcome,
    WorkloadComparison,
    run_engine_tournament,
)


def test_tournament_requires_exact_authority_before_admission() -> None:
    reference = EngineKernel(
        engine_name="reference",
        geometry=KernelGeometry.SPARSE_DELTA_CLOSURE,
        run=lambda value: KernelOutcome(authority=value + 1),
    )
    candidate = EngineKernel(
        engine_name="zelph",
        geometry=KernelGeometry.SPARSE_DELTA_CLOSURE,
        run=lambda value: KernelOutcome(authority=value + 2),
    )

    receipt = run_engine_tournament(
        reference=reference,
        candidate=candidate,
        workloads=(1, 2),
        repeats=1,
    )

    assert receipt.authority_exact is False
    assert receipt.earns_keep is False
    assert receipt.promotion_ready is False


def test_tournament_accepts_caller_supplied_relational_equivalence() -> None:
    reference = EngineKernel(
        engine_name="reference",
        geometry=KernelGeometry.GLOBAL_INDEXED_EXPOSURE,
        run=lambda value: KernelOutcome(authority=(value, value + 1)),
    )
    candidate = EngineKernel(
        engine_name="postgresql",
        geometry=KernelGeometry.GLOBAL_INDEXED_EXPOSURE,
        run=lambda value: KernelOutcome(authority=(value + 1, value)),
    )

    receipt = run_engine_tournament(
        reference=reference,
        candidate=candidate,
        workloads=(3,),
        equivalent=lambda left, right: set(left) == set(right),
        repeats=1,
    )

    assert receipt.authority_exact is True


def test_promotion_requires_no_worse_work_and_strict_wall_witness() -> None:
    comparison = WorkloadComparison(
        workload_ordinal=0,
        authority_equivalent=True,
        reference_wall_ns=100,
        candidate_wall_ns=80,
        reference_cpu_ns=90,
        candidate_cpu_ns=70,
        reference_boundary_crossings=10,
        candidate_boundary_crossings=2,
        reference_bytes_read=1_000,
        candidate_bytes_read=500,
        reference_bytes_written=800,
        candidate_bytes_written=400,
    )
    receipt = EngineTournamentReceipt(
        reference_engine="custom-worklist",
        candidate_engine="zelph",
        geometry=KernelGeometry.SPARSE_DELTA_CLOSURE,
        repeats=5,
        comparisons=(comparison,),
    )

    assert receipt.authority_exact is True
    assert receipt.earns_keep is True
    assert receipt.promotion_ready is True


def test_more_boundary_crossings_block_engine_admission() -> None:
    comparison = WorkloadComparison(
        workload_ordinal=0,
        authority_equivalent=True,
        reference_wall_ns=100,
        candidate_wall_ns=80,
        reference_cpu_ns=90,
        candidate_cpu_ns=70,
        reference_boundary_crossings=2,
        candidate_boundary_crossings=3,
        reference_bytes_read=0,
        candidate_bytes_read=0,
        reference_bytes_written=0,
        candidate_bytes_written=0,
    )
    receipt = EngineTournamentReceipt(
        reference_engine="packed-native",
        candidate_engine="postgresql",
        geometry=KernelGeometry.LOCAL_BOUNDED_FIBRE,
        repeats=3,
        comparisons=(comparison,),
    )

    assert receipt.earns_keep is False
    assert receipt.promotion_ready is False
