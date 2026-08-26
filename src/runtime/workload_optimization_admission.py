"""Workload-fit admission for physical optimization backends.

A backend is never promoted because it is theoretically faster, more packed, or
more parallel. Promotion is based on exact semantic authority plus measured
end-to-end work on the actual workload, including setup, packing/repacking,
dispatch, transfer, and useful kernel work.

This keeps "Ferrari for grocery shopping" failures explicit: a candidate may
have excellent inner-kernel throughput and still lose once boundary costs are
included.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BackendFamily(str, Enum):
    PACKED_SCALAR = "packed-scalar"
    BATCH_VECTOR = "batch-vector"
    NATIVE_SWAR = "native-swar"
    ACCELERATOR = "accelerator"


@dataclass(frozen=True, slots=True)
class WorkloadShape:
    item_count: int
    mean_fibre_items: float
    homogeneous: bool
    already_candidate_native: bool
    repacking_required: bool
    useful_operations: int

    def __post_init__(self) -> None:
        if self.item_count < 0:
            raise ValueError("item_count must be non-negative")
        if self.mean_fibre_items < 0:
            raise ValueError("mean_fibre_items must be non-negative")
        if self.useful_operations < 0:
            raise ValueError("useful_operations must be non-negative")


@dataclass(frozen=True, slots=True)
class BackendMeasurement:
    family: BackendFamily
    authority_equal: bool
    setup_ns: int
    repack_ns: int
    dispatch_ns: int
    transfer_ns: int
    kernel_ns: int
    total_ns: int

    def __post_init__(self) -> None:
        for name in (
            "setup_ns",
            "repack_ns",
            "dispatch_ns",
            "transfer_ns",
            "kernel_ns",
            "total_ns",
        ):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be non-negative")
        accounted = (
            self.setup_ns
            + self.repack_ns
            + self.dispatch_ns
            + self.transfer_ns
            + self.kernel_ns
        )
        if accounted > self.total_ns:
            raise ValueError("measured component time cannot exceed total_ns")

    @property
    def boundary_ns(self) -> int:
        return self.setup_ns + self.repack_ns + self.dispatch_ns + self.transfer_ns

    @property
    def boundary_fraction(self) -> float:
        if self.total_ns == 0:
            return 0.0
        return self.boundary_ns / self.total_ns


@dataclass(frozen=True, slots=True)
class OptimizationAdmissionReceipt:
    workload: WorkloadShape
    reference: BackendMeasurement
    candidate: BackendMeasurement
    minimum_improvement: float = 0.10

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum_improvement < 1.0:
            raise ValueError("minimum_improvement must be in [0, 1)")

    @property
    def authority_exact(self) -> bool:
        return self.reference.authority_equal and self.candidate.authority_equal

    @property
    def end_to_end_improvement(self) -> float:
        if self.reference.total_ns == 0:
            return 0.0 if self.candidate.total_ns == 0 else float("-inf")
        return (self.reference.total_ns - self.candidate.total_ns) / self.reference.total_ns

    @property
    def structurally_plausible(self) -> bool:
        """Cheap pre-admission filter; it is not a promotion decision.

        Packed scalar is the reference and is always plausible. Batch/vector
        candidates need homogeneous work. Native SWAR additionally needs the
        data to already be in the candidate's native packed representation so
        repacking is not the workload. Accelerators require homogeneous work
        and no compulsory per-fibre repacking/transfer cycle.
        """

        family = self.candidate.family
        if family is BackendFamily.PACKED_SCALAR:
            return True
        if family is BackendFamily.BATCH_VECTOR:
            return self.workload.homogeneous
        if family is BackendFamily.NATIVE_SWAR:
            return (
                self.workload.homogeneous
                and self.workload.already_candidate_native
                and not self.workload.repacking_required
            )
        if family is BackendFamily.ACCELERATOR:
            return self.workload.homogeneous and not self.workload.repacking_required
        return False

    @property
    def promoted(self) -> bool:
        return (
            self.authority_exact
            and self.structurally_plausible
            and self.end_to_end_improvement >= self.minimum_improvement
        )

    @property
    def reason(self) -> str:
        if not self.authority_exact:
            return "semantic-authority-mismatch"
        if not self.structurally_plausible:
            return "workload-geometry-does-not-amortize-candidate-boundaries"
        if self.end_to_end_improvement < self.minimum_improvement:
            return "measured-end-to-end-improvement-below-gate"
        return "promoted"

    def as_dict(self) -> dict[str, object]:
        return {
            "contract": "sensiblaw.workload-optimization-admission.v0_1",
            "reference_family": self.reference.family.value,
            "candidate_family": self.candidate.family.value,
            "authority_exact": self.authority_exact,
            "structurally_plausible": self.structurally_plausible,
            "minimum_improvement": self.minimum_improvement,
            "end_to_end_improvement": self.end_to_end_improvement,
            "reference_boundary_fraction": self.reference.boundary_fraction,
            "candidate_boundary_fraction": self.candidate.boundary_fraction,
            "promoted": self.promoted,
            "reason": self.reason,
        }


__all__ = [
    "BackendFamily",
    "BackendMeasurement",
    "OptimizationAdmissionReceipt",
    "WorkloadShape",
]
