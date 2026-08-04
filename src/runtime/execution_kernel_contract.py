"""Mandatory execution-kernel contracts for bounded semantic work.

Semantic functions remain pure.  This module governs only physical kernels that
can loop, wait, allocate materially, checkpoint, or mutate durable execution
state.  Contracts turn progress/lifecycle/authority telemetry into executable
invariants instead of advisory labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from time import monotonic_ns
from typing import Any, Mapping, Sequence


KERNEL_CONTRACT_SCHEMA_VERSION = "sensiblaw.execution-kernel-contract.v1"
KERNEL_EVENT_SCHEMA_VERSION = "sensiblaw.execution-kernel-event.v1"


class KernelAuthority(StrEnum):
    MEMORY = "memory"
    CHECKPOINT = "checkpoint"
    POSTGRESQL = "postgresql"


class KernelContractViolation(RuntimeError):
    """An execution event violated its registered physical contract."""

    def __init__(self, diagnostic: Mapping[str, Any]):
        self.diagnostic = dict(diagnostic)
        super().__init__(
            f"execution kernel contract violation: "
            f"{self.diagnostic.get('kernel_key')} / "
            f"{self.diagnostic.get('violation')}"
        )


@dataclass(frozen=True)
class KernelContract:
    key: str
    stage_prefixes: tuple[str, ...]
    lifecycle: str
    budget_family: str
    authority: KernelAuthority
    progress_keys: tuple[str, ...]
    progress_unit: str
    max_batch_size: int
    checkpoint_contract: str
    allowed_next: tuple[str, ...]
    no_progress_timeout_seconds: int = 120
    forbid_post_drain_admission: bool = False

    def __post_init__(self) -> None:
        if not self.key or not self.stage_prefixes:
            raise ValueError("kernel key and stage prefixes are required")
        if self.max_batch_size < 1 or self.no_progress_timeout_seconds < 1:
            raise ValueError("kernel bounds must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": KERNEL_CONTRACT_SCHEMA_VERSION,
            "key": self.key,
            "stage_prefixes": list(self.stage_prefixes),
            "lifecycle": self.lifecycle,
            "budget_family": self.budget_family,
            "authority": self.authority.value,
            "progress_keys": list(self.progress_keys),
            "progress_unit": self.progress_unit,
            "max_batch_size": self.max_batch_size,
            "checkpoint_contract": self.checkpoint_contract,
            "allowed_next": list(self.allowed_next),
            "no_progress_timeout_seconds": self.no_progress_timeout_seconds,
            "forbid_post_drain_admission": self.forbid_post_drain_admission,
        }


@dataclass
class _KernelState:
    last_progress: int | None = None
    last_progress_ns: int = field(default_factory=monotonic_ns)
    last_phase: str | None = None
    completed: bool = False


def _normalise(value: str) -> str:
    return str(value).strip().lower().replace("-", "_")


DEFAULT_KERNEL_CONTRACTS: tuple[KernelContract, ...] = (
    KernelContract(
        key="typing.leaf-execution",
        stage_prefixes=("local_typing_diagnostics", "typing_"),
        lifecycle="typing",
        budget_family="typing",
        authority=KernelAuthority.CHECKPOINT,
        progress_keys=("leaves_completed", "output_items_completed", "completed"),
        progress_unit="typing_leaf",
        max_batch_size=4096,
        checkpoint_contract="typing-leaf-hierarchy:v1",
        allowed_next=("closure.activation", "failed"),
    ),
    KernelContract(
        key="closure.activation",
        stage_prefixes=("activation_", "closure_activation"),
        lifecycle="producing",
        budget_family="closure",
        authority=KernelAuthority.CHECKPOINT,
        progress_keys=("leaves_completed", "admitted_delta_count", "completed"),
        progress_unit="activation_leaf",
        max_batch_size=4096,
        checkpoint_contract="closure-activation-leaves:v1",
        allowed_next=("closure.handoff", "closure.execution", "failed"),
    ),
    KernelContract(
        key="closure.handoff",
        stage_prefixes=("owner_admission_batch", "owner_frontier_reconstruction"),
        lifecycle="draining",
        budget_family="closure",
        authority=KernelAuthority.POSTGRESQL,
        progress_keys=(
            "durable_admissions",
            "new_durable_obligations",
            "owner_revision",
        ),
        progress_unit="owner_revision",
        max_batch_size=4096,
        checkpoint_contract="postgres-semantic-owner-stream:v1",
        allowed_next=("closure.reducing-final-dirty", "closure.execution", "failed"),
        no_progress_timeout_seconds=120,
        forbid_post_drain_admission=True,
    ),
    KernelContract(
        key="closure.execution",
        stage_prefixes=(
            "streaming_closure",
            "closure_",
            "job_",
            "ready_frontier_",
            "scheduled_job_",
            "dirty_group_",
            "base_proposal_",
            "composition_",
        ),
        lifecycle="draining",
        budget_family="closure",
        authority=KernelAuthority.POSTGRESQL,
        progress_keys=("jobs_completed", "completed", "owner_revision"),
        progress_unit="semantic_job",
        max_batch_size=4096,
        checkpoint_contract="postgres-fenced-semantic-worker:v1",
        allowed_next=(
            "closure.reducing-final-dirty",
            "finalization.materialize",
            "failed",
        ),
    ),
    KernelContract(
        key="closure.reducing-final-dirty",
        stage_prefixes=("reduce_dirty", "final_dirty", "dirty_group_reduction"),
        lifecycle="reducing_final_dirty",
        budget_family="closure",
        authority=KernelAuthority.POSTGRESQL,
        progress_keys=("dirty_groups_completed", "owner_revision", "completed"),
        progress_unit="owner_key",
        max_batch_size=4096,
        checkpoint_contract="postgres-owner-reduction:v1",
        allowed_next=("finalization.materialize", "failed"),
    ),
    KernelContract(
        key="finalization.materialize",
        stage_prefixes=("materialize_", "assemble_reduction", "build_convergent_"),
        lifecycle="certifying",
        budget_family="finalization",
        authority=KernelAuthority.POSTGRESQL,
        progress_keys=("processed", "rows_scanned", "completed"),
        progress_unit="settled_reduction_row",
        max_batch_size=4096,
        checkpoint_contract="indexed-settled-owner-reductions:v1",
        allowed_next=("finalization.certify", "serialization.receipt", "failed"),
    ),
    KernelContract(
        key="finalization.certify",
        stage_prefixes=("build_region_boundary_", "validate_", "build_fixed_point_"),
        lifecycle="certifying",
        budget_family="finalization",
        authority=KernelAuthority.POSTGRESQL,
        progress_keys=("processed", "rows_scanned", "completed"),
        progress_unit="certificate_component",
        max_batch_size=4096,
        checkpoint_contract="document-fixed-point-certificate:v1",
        allowed_next=("serialization.receipt", "failed"),
    ),
    KernelContract(
        key="serialization.receipt",
        stage_prefixes=("serialize_", "isolated_serializer", "release_owner_"),
        lifecycle="certifying",
        budget_family="serialization",
        authority=KernelAuthority.CHECKPOINT,
        progress_keys=("processed", "bytes_written", "completed"),
        progress_unit="receipt_segment",
        max_batch_size=4096,
        checkpoint_contract="reference-execution-receipt:v1",
        allowed_next=("publication.postgresql", "failed"),
    ),
    KernelContract(
        key="publication.postgresql",
        stage_prefixes=("postgres_", "publication_"),
        lifecycle="publishing",
        budget_family="publication",
        authority=KernelAuthority.POSTGRESQL,
        progress_keys=("rows_persisted", "completed", "publication_revision"),
        progress_unit="publication_row",
        max_batch_size=4096,
        checkpoint_contract="postgres-publication-build:v1",
        allowed_next=("parity.acceptance", "completed", "failed"),
    ),
    KernelContract(
        key="parity.acceptance",
        stage_prefixes=(
            "acceptance_",
            "semantic_parity",
            "reference_parity",
            "parity_",
        ),
        lifecycle="verifying",
        budget_family="parity",
        authority=KernelAuthority.POSTGRESQL,
        progress_keys=("manifests_verified", "completed"),
        progress_unit="manifest",
        max_batch_size=4096,
        checkpoint_contract="manifest-first-parity:v1",
        allowed_next=("completed", "failed"),
    ),
)


class KernelRegistry:
    def __init__(self, contracts: Sequence[KernelContract] = DEFAULT_KERNEL_CONTRACTS):
        self.contracts = tuple(contracts)
        self._states: dict[str, _KernelState] = {}
        self._active_kernel: str | None = None

    def resolve(self, stage: str) -> KernelContract:
        normalised = _normalise(stage).split(":", 1)[0]
        matches = [
            contract
            for contract in self.contracts
            if any(
                normalised.startswith(_normalise(prefix))
                for prefix in contract.stage_prefixes
            )
        ]
        if not matches:
            raise KernelContractViolation(
                {
                    "schema_version": KERNEL_EVENT_SCHEMA_VERSION,
                    "kernel_key": None,
                    "stage": stage,
                    "violation": "unregistered_execution_kernel",
                }
            )
        return max(
            matches,
            key=lambda contract: max(
                len(prefix)
                for prefix in contract.stage_prefixes
                if normalised.startswith(_normalise(prefix))
            ),
        )

    @staticmethod
    def _progress_value(
        contract: KernelContract, counts: Mapping[str, int]
    ) -> int | None:
        for key in contract.progress_keys:
            if key in counts:
                return int(counts[key])
        return None

    def observe(
        self,
        *,
        stage: str,
        phase: str,
        counts: Mapping[str, int] | None,
        details: Mapping[str, Any] | None,
        budget_family: str,
    ) -> dict[str, Any]:
        contract = self.resolve(stage)
        count_values = {str(key): int(value) for key, value in (counts or {}).items()}
        detail_values = dict(details or {})
        now = monotonic_ns()
        state = self._states.setdefault(contract.key, _KernelState())
        violation: str | None = None

        if budget_family != contract.budget_family:
            violation = "budget_family_mismatch"

        batch_size = int(
            detail_values.get("batch_size") or count_values.get("rows_in") or 0
        )
        if batch_size > contract.max_batch_size:
            violation = violation or "batch_bound_exceeded"

        reported_authority = str(detail_values.get("authority_backend") or "")
        authority_rows = int(detail_values.get("authority_row_count") or 0)
        if contract.authority is KernelAuthority.POSTGRESQL and (
            reported_authority != KernelAuthority.POSTGRESQL.value or authority_rows < 1
        ):
            violation = violation or "postgresql_authority_missing"

        frontier_drained = bool(detail_values.get("frontier_drained"))
        rows_in = int(count_values.get("rows_in") or 0)
        new_obligations = int(count_values.get("new_durable_obligations") or 0)
        if (
            contract.forbid_post_drain_admission
            and frontier_drained
            and rows_in > 0
            and new_obligations <= 0
        ):
            violation = violation or "post_drain_admission_without_durable_obligation"

        progress = self._progress_value(contract, count_values)
        waiting = (
            phase.endswith("waiting") or detail_values.get("wait_reason") is not None
        )
        completed = bool(
            detail_values.get("completed")
            or phase.endswith("completed")
            or (
                count_values.get("total") is not None
                and count_values.get("completed") == count_values.get("total")
            )
        )
        if waiting and (
            not detail_values.get("wait_reason")
            or not detail_values.get("wait_dependency")
        ):
            violation = violation or "unnamed_wait"

        if progress is not None and (
            state.last_progress is None or progress > state.last_progress
        ):
            state.last_progress = progress
            state.last_progress_ns = now
        elif (
            not completed
            and now - state.last_progress_ns
            > contract.no_progress_timeout_seconds * 1_000_000_000
        ):
            violation = violation or "no_monotonic_progress"

        if self._active_kernel and self._active_kernel != contract.key:
            previous = next(
                row for row in self.contracts if row.key == self._active_kernel
            )
            if contract.key not in previous.allowed_next:
                violation = violation or "illegal_lifecycle_transition"
        self._active_kernel = contract.key
        state.last_phase = phase
        state.completed = completed

        event = {
            "schema_version": KERNEL_EVENT_SCHEMA_VERSION,
            "kernel_key": contract.key,
            "stage": stage,
            "phase": phase,
            "lifecycle": contract.lifecycle,
            "budget_family": contract.budget_family,
            "authority": contract.authority.value,
            "progress_unit": contract.progress_unit,
            "progress": progress,
            "batch_size": batch_size,
            "frontier_drained": frontier_drained,
            "new_durable_obligations": new_obligations,
            "checkpoint_contract": contract.checkpoint_contract,
            "violation": violation,
            "contract": contract.to_dict(),
        }
        if violation is not None:
            raise KernelContractViolation(event)
        return event


__all__ = [
    "DEFAULT_KERNEL_CONTRACTS",
    "KERNEL_CONTRACT_SCHEMA_VERSION",
    "KERNEL_EVENT_SCHEMA_VERSION",
    "KernelAuthority",
    "KernelContract",
    "KernelContractViolation",
    "KernelRegistry",
]
