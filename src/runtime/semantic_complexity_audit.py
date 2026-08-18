"""Executable structural-complexity contracts for the numeric semantic runtime.

This module does *not* claim to compute Kolmogorov complexity.  Exact K(x) is
uncomputable.  It instead exposes conservative, directly measurable surrogates
that let runtime implementations be checked against the formal ITIR/PNF rule:
a consumer should carry and revisit no more state than is sufficient for its
observable future dynamics.

The key distinction is between description exposure and transition exposure:

* ``OperationalCarrierCost`` counts represented structure;
* ``FrontierWorkCertificate`` asks whether one transition is bounded by the
  active frontier plus the dependency edges actually touched;
* ``repeated_full_fibre_exposure`` makes cumulative re-scanning visible rather
  than hiding it behind a small final carrier.

All checks fail closed when semantic sufficiency/provenance preservation has not
been supplied by the caller.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Iterable, Literal

AuditState = Literal["verified", "violated", "indeterminate"]


@dataclass(frozen=True, slots=True)
class OperationalCarrierCost:
    """A unit-weight description-length surrogate for a represented carrier.

    The fields deliberately correspond to quantities already exposed by numeric
    PNF interfaces.  ``encoded_units`` is caller-normalised (for example bytes,
    rows, or fixed-size words); this module never silently converts between
    incomparable physical units.
    """

    nodes: int = 0
    edges: int = 0
    residuals: int = 0
    encoded_units: int = 0
    boundary_demands: int = 0

    def __post_init__(self) -> None:
        if min(
            self.nodes,
            self.edges,
            self.residuals,
            self.encoded_units,
            self.boundary_demands,
        ) < 0:
            raise ValueError("operational carrier counts must be non-negative")

    @property
    def unit_cost(self) -> int:
        return (
            self.nodes
            + self.edges
            + self.residuals
            + self.encoded_units
            + self.boundary_demands
        )


@dataclass(frozen=True, slots=True)
class ConsumerSufficientCompression:
    """Evidence that a smaller carrier is admissible for one consumer.

    ``consumer_factorizes`` means the consumer's observation is unchanged by
    replacing the source carrier by the projection.  ``residuals_preserved``
    and ``provenance_preserved`` prevent a cheap but destructive projection from
    being reported as an optimisation.
    """

    source: OperationalCarrierCost
    projected: OperationalCarrierCost
    consumer_factorizes: bool | None
    residuals_preserved: bool | None
    provenance_preserved: bool | None

    @property
    def state(self) -> AuditState:
        evidence = (
            self.consumer_factorizes,
            self.residuals_preserved,
            self.provenance_preserved,
        )
        if any(value is None for value in evidence):
            return "indeterminate"
        if not all(evidence):
            return "violated"
        if self.projected.unit_cost > self.source.unit_cost:
            return "violated"
        return "verified"

    @property
    def saved_units(self) -> int | None:
        if self.state != "verified":
            return None
        return self.source.unit_cost - self.projected.unit_cost

    def to_mapping(self) -> dict[str, object]:
        return {
            "state": self.state,
            "source": asdict(self.source),
            "projected": asdict(self.projected),
            "source_unit_cost": self.source.unit_cost,
            "projected_unit_cost": self.projected.unit_cost,
            "saved_units": self.saved_units,
            "consumer_factorizes": self.consumer_factorizes,
            "residuals_preserved": self.residuals_preserved,
            "provenance_preserved": self.provenance_preserved,
            "claim": "operational_surrogate_not_kolmogorov_complexity",
        }


@dataclass(frozen=True, slots=True)
class FrontierWorkCertificate:
    """Check whether one transition is bounded by its sufficient active workset."""

    active_frontier: int
    touched_edges: int
    measured_work: int | None
    full_carrier: int | None = None

    def __post_init__(self) -> None:
        for value in (
            self.active_frontier,
            self.touched_edges,
            self.measured_work,
            self.full_carrier,
        ):
            if value is not None and value < 0:
                raise ValueError("work counts must be non-negative")

    @property
    def sufficient_work_bound(self) -> int:
        return self.active_frontier + self.touched_edges

    @property
    def state(self) -> AuditState:
        if self.measured_work is None:
            return "indeterminate"
        return (
            "verified"
            if self.measured_work <= self.sufficient_work_bound
            else "violated"
        )

    @property
    def full_carrier_fraction(self) -> Fraction | None:
        if self.measured_work is None or not self.full_carrier:
            return None
        return Fraction(self.measured_work, self.full_carrier)


@dataclass(frozen=True, slots=True)
class FibreScanExposure:
    """Physical scan exposure for append waves entering one logical owner fibre."""

    wave_sizes: tuple[int, ...]
    final_fibre_size: int
    repeated_full_fibre_units: int
    append_only_units: int

    @property
    def avoidable_rescan_units(self) -> int:
        return self.repeated_full_fibre_units - self.append_only_units

    @property
    def amplification(self) -> Fraction | None:
        if self.append_only_units == 0:
            return None
        return Fraction(self.repeated_full_fibre_units, self.append_only_units)


def repeated_full_fibre_exposure(wave_sizes: Iterable[int]) -> FibreScanExposure:
    """Expose the cost of reducing the whole accumulated fibre after each wave.

    For unit waves of length ``k`` this is the triangular exposure
    ``1 + 2 + ... + k`` versus ``k`` append-only units.  The function is merely
    an accounting witness: it does not assert that an incremental reducer is
    semantically valid.  That requires a separate factorisation/commutation
    proof for the concrete reduction.
    """

    waves = tuple(int(value) for value in wave_sizes)
    if any(value < 0 for value in waves):
        raise ValueError("fibre wave sizes must be non-negative")
    cumulative = 0
    exposure = 0
    for value in waves:
        cumulative += value
        exposure += cumulative
    return FibreScanExposure(
        wave_sizes=waves,
        final_fibre_size=cumulative,
        repeated_full_fibre_units=exposure,
        append_only_units=sum(waves),
    )


__all__ = [
    "AuditState",
    "ConsumerSufficientCompression",
    "FibreScanExposure",
    "FrontierWorkCertificate",
    "OperationalCarrierCost",
    "repeated_full_fibre_exposure",
]
