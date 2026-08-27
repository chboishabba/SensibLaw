"""Native execution-only timing for delta-fed local reducers.

This module deliberately does not participate in semantic identity, authority
hashes, admissibility, or parity.  It supplies opt-in monotonic nanosecond
measurements for the reusable execution shape::

    DeltaSource
    -> ProjectionAtoms
    -> AffectedKeys
    -> LocalReducer
    -> AuthorityPublication

The recorder is intentionally cheap when disabled and composes with the existing
accepted-metric ledger, which owns parser/post-parser occupancy acceptance.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
import os
from time import monotonic_ns
from typing import Any, Iterator


DELTA_EXECUTION_TIMING_REF = "sensiblaw.delta-execution-timing.v0_1"
DELTA_EXECUTION_TIMING_ENV = "SENSIBLAW_NATIVE_DELTA_TIMING"


class DeltaTimingStage(StrEnum):
    SOURCE_DELTA = "source_delta"
    PROJECTION_ATOMS = "projection_atoms"
    AFFECTED_KEYS = "affected_keys"
    LOCAL_REDUCER = "local_reducer"
    AUTHORITY_PUBLICATION = "authority_publication"


def native_delta_timing_enabled() -> bool:
    raw = os.environ.get(DELTA_EXECUTION_TIMING_ENV)
    if raw is None:
        return False
    return raw.strip().lower() not in {"", "0", "false", "no", "off"}


@dataclass(frozen=True, slots=True)
class DeltaTimingObservation:
    stage: DeltaTimingStage
    owner_ref: str
    fibre_ref: str | None
    elapsed_ns: int
    input_work_units: int | None = None
    output_work_units: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "owner_ref": self.owner_ref,
            "fibre_ref": self.fibre_ref,
            "elapsed_ns": self.elapsed_ns,
            "input_work_units": self.input_work_units,
            "output_work_units": self.output_work_units,
        }


@dataclass(slots=True)
class DeltaExecutionTimingLedger:
    enabled: bool = field(default_factory=native_delta_timing_enabled)
    observations: list[DeltaTimingObservation] = field(default_factory=list)

    def record(
        self,
        *,
        stage: DeltaTimingStage,
        owner_ref: str,
        fibre_ref: str | None,
        elapsed_ns: int,
        input_work_units: int | None = None,
        output_work_units: int | None = None,
    ) -> None:
        if not self.enabled:
            return
        if elapsed_ns < 0:
            raise ValueError("elapsed_ns must be non-negative")
        for value, name in (
            (input_work_units, "input_work_units"),
            (output_work_units, "output_work_units"),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        self.observations.append(
            DeltaTimingObservation(
                stage=stage,
                owner_ref=owner_ref,
                fibre_ref=fibre_ref,
                elapsed_ns=elapsed_ns,
                input_work_units=input_work_units,
                output_work_units=output_work_units,
            )
        )

    @contextmanager
    def measure(
        self,
        *,
        stage: DeltaTimingStage,
        owner_ref: str,
        fibre_ref: str | None = None,
        input_work_units: int | None = None,
        output_work_units: int | None = None,
    ) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        started = monotonic_ns()
        try:
            yield
        finally:
            self.record(
                stage=stage,
                owner_ref=owner_ref,
                fibre_ref=fibre_ref,
                elapsed_ns=monotonic_ns() - started,
                input_work_units=input_work_units,
                output_work_units=output_work_units,
            )

    def stage_totals_ns(self) -> dict[str, int]:
        totals = {stage.value: 0 for stage in DeltaTimingStage}
        for observation in self.observations:
            totals[observation.stage.value] += observation.elapsed_ns
        return totals

    def owner_totals_ns(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for observation in self.observations:
            totals[observation.owner_ref] = (
                totals.get(observation.owner_ref, 0) + observation.elapsed_ns
            )
        return totals

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": DELTA_EXECUTION_TIMING_REF,
            "enabled": self.enabled,
            "semantic_authority_effect": "none",
            "semantic_identity_effect": "none",
            "clock": "time.monotonic_ns",
            "stage_totals_ns": self.stage_totals_ns(),
            "owner_totals_ns": self.owner_totals_ns(),
            "observations": [row.to_dict() for row in self.observations],
        }


__all__ = [
    "DELTA_EXECUTION_TIMING_ENV",
    "DELTA_EXECUTION_TIMING_REF",
    "DeltaExecutionTimingLedger",
    "DeltaTimingObservation",
    "DeltaTimingStage",
    "native_delta_timing_enabled",
]
