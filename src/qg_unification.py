"""Prototype SL boundary adapter for DA51 trace ingestion.

This module implements the first executable step from the QG unification
contract:
- parse/validate the DA51Trace payload shape
- project it into the canonical TraceVector schema
- build a typed dependency envelope for downstream adapters

The implementation is intentionally conservative and currently does not mutate
canonical proof semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any, Dict, Iterable, List, Mapping, Optional


@dataclass(frozen=True)
class DA51Trace:
    """Normalized input shape expected from DA51-compatible producers."""

    da51: str
    exponents: List[int]
    hot: int
    cold: int
    mass: int
    steps: int
    basin: int
    j_fixed: bool

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "DA51Trace":
        """Parse and validate a mapping into a strongly-typed DA51Trace."""
        required = {"da51", "exponents", "hot", "cold", "mass", "steps", "basin", "j_fixed"}
        missing = sorted(required - set(payload.keys()))
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")

        exponents_raw = payload["exponents"]
        if not isinstance(exponents_raw, Iterable):
            raise ValueError("exponents must be an iterable of integers")
        exponents = list(exponents_raw)
        if len(exponents) != 15:
            raise ValueError(f"exponents must have exactly 15 elements, got {len(exponents)}")
        if not all(isinstance(item, int) for item in exponents):
            raise ValueError("all exponents must be integers")

        return cls(
            da51=str(payload["da51"]),
            exponents=exponents,
            hot=int(payload["hot"]),
            cold=int(payload["cold"]),
            mass=int(payload["mass"]),
            steps=int(payload["steps"]),
            basin=int(payload["basin"]),
            j_fixed=bool(payload["j_fixed"]),
        )


@dataclass(frozen=True)
class TraceVector:
    """Canonical SL trace envelope emitted by this adapter."""

    id: str
    exponents: List[int]
    normalized: List[float]
    mass: int
    sparsity: float
    hot: int
    cold: int
    steps: int
    basin: int
    j_fixed: bool
    mdls: Optional[Dict[str, float]]
    admissible: bool


def normalize_exponents(exponents: List[int]) -> List[float]:
    """Project integer exponents to S^14 coordinates with deterministic scaling."""
    norm = sqrt(sum(value * value for value in exponents))
    if norm == 0:
        return [0.0 for _ in exponents]
    return [float(value) / norm for value in exponents]


def compute_sparsity(exponents: List[int]) -> float:
    """Return fraction of exact-zero entries in the exponent vector."""
    if not exponents:
        return 0.0
    zero_count = sum(1 for value in exponents if value == 0)
    return float(zero_count) / float(len(exponents))


def is_admissible(trace: DA51Trace, normalized: List[float]) -> bool:
    """Conservative admissibility predicate used for adapter gating.

    This does not impose domain semantics; it ensures structural sanity.
    """
    if len(trace.exponents) != len(normalized):
        return False
    if trace.mass < 0 or trace.steps < 0 or trace.basin < 0:
        return False
    return all(isinstance(v, int) for v in trace.exponents)


def as_trace_vector(payload: Mapping[str, Any]) -> TraceVector:
    """Convert a DA51 payload to the canonical SL TraceVector projection."""
    trace = DA51Trace.from_mapping(payload)
    normalized = normalize_exponents(trace.exponents)
    mdls = {
        "norm": sum(float(value * value) for value in trace.exponents) ** 0.5,
        "sum_abs": float(sum(abs(value) for value in trace.exponents)),
        "max_abs": float(max(abs(value) for value in trace.exponents)) if trace.exponents else 0.0,
    }
    admissible = is_admissible(trace, normalized)

    return TraceVector(
        id=trace.da51,
        exponents=list(trace.exponents),
        normalized=normalized,
        mass=trace.mass,
        sparsity=compute_sparsity(trace.exponents),
        hot=trace.hot,
        cold=trace.cold,
        steps=trace.steps,
        basin=trace.basin,
        j_fixed=trace.j_fixed,
        mdls=mdls,
        admissible=admissible,
    )


def build_dependency_span_payload(trace: TraceVector) -> Dict[str, Any]:
    """Emit a strict typed envelope intended for adapter adapters downstream."""
    return {
        "schema_version": "qg_unification.trace_vector.v1",
        "source": "da51",
        "sink": "sensiblaw",
        "envelope": {
            "id": trace.id,
            "exponents": trace.exponents,
            "normalized": trace.normalized,
            "mass": trace.mass,
            "sparsity": trace.sparsity,
            "hot": trace.hot,
            "cold": trace.cold,
            "steps": trace.steps,
            "basin": trace.basin,
            "j_fixed": trace.j_fixed,
            "mdls": trace.mdls,
            "admissible": trace.admissible,
        },
    }
