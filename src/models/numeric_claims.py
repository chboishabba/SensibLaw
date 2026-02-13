from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from typing import Iterable, List, Optional, Sequence, Tuple


_UNIT_ALIASES = {
    "%": "percent",
    "per cent": "percent",
    "usd": "usd",
    "dollars": "usd",
    "dollar": "usd",
}

_SCALE_EXPONENT = {
    "k": 3,
    "thousand": 3,
    "m": 6,
    "million": 6,
    "b": 9,
    "billion": 9,
    "t": 12,
    "trillion": 12,
}

_PRIORITY_DIMENSIONS = {"currency", "population", "military_count", "approval_percent"}


class AnchorStatus(str, Enum):
    TRANSIENT = "transient"
    CANDIDATE = "candidate"
    ANCHOR = "anchor"


class ClaimRelation(str, Enum):
    EXACT = "exact"
    COMPATIBLE = "compatible"
    CONFLICT = "conflict"
    UNRELATED = "unrelated"


@dataclass(frozen=True)
class Magnitude:
    value: Decimal
    unit: str
    dimension: str = "unknown"

    @property
    def id(self) -> str:
        return magnitude_id(self.value, self.unit)


@dataclass(frozen=True)
class QuantifiedClaim:
    id: str
    magnitude_id: str
    subject_id: str
    actor_id: str
    predicate: str
    time_scope: str
    modality: str
    significant_figures: int
    lower_bound: Decimal
    upper_bound: Decimal
    source_event_id: str


@dataclass(frozen=True)
class RangeClaim:
    id: str
    lower_magnitude_id: str
    upper_magnitude_id: str
    subject_id: str
    actor_id: str
    predicate: str
    time_scope: str
    modality: str
    source_event_id: str


@dataclass(frozen=True)
class RatioClaim:
    id: str
    numerator_magnitude_id: str
    denominator_magnitude_id: str
    subject_id: str
    actor_id: str
    predicate: str
    time_scope: str
    source_event_id: str


@dataclass(frozen=True)
class NumericSurface:
    id: str
    claim_id: str
    original_text: str
    currency_symbol_present: bool
    compact_suffix_present: bool
    scale_word_present: bool
    spacing_variant: str
    thousands_separator_used: bool
    format_variant_code: str


@dataclass(frozen=True)
class MagnitudeUsage:
    recurrence_count: int
    cross_actor_count: int
    boundary_usage_count: int = 0
    dimension: str = "unknown"


@dataclass(frozen=True)
class GraduationPolicy:
    recurrence_threshold: int = 3
    cross_actor_threshold: int = 2
    boundary_usage_threshold: int = 1
    priority_dimensions: frozenset[str] = frozenset(_PRIORITY_DIMENSIONS)


@dataclass(frozen=True)
class AuthorityEdge:
    src: str
    predicate: str
    dst: str


def normalize_unit(unit: str) -> str:
    u = re.sub(r"\s+", " ", str(unit or "").strip().lower())
    if not u:
        return ""
    return _UNIT_ALIASES.get(u, u)


def normalize_decimal_text(value: Decimal) -> str:
    if value.is_nan() or value.is_infinite():
        raise ValueError("non-finite decimal is not supported")
    out = format(value.normalize(), "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    if out == "-0":
        out = "0"
    return out


def magnitude_id(value: Decimal, unit: str) -> str:
    return f"mag:{normalize_decimal_text(value)}|{normalize_unit(unit)}"


def significant_figures_from_surface(surface: str) -> int:
    s = str(surface or "").strip().lower()
    if not s:
        return 0
    s = s.replace(",", "")
    s = re.sub(r"\bper\s+cent\b", "percent", s)
    s = s.lstrip("+$-")

    # Strip known suffix/units so we count only value digits.
    s = re.sub(r"\b(percent|usd|dollars?|thousand|million|billion|trillion)\b", "", s).strip()
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)(?:[kmbt])?$", s)
    if not m:
        return 0
    num = m.group(1)
    if not num:
        return 0

    if "." in num:
        whole, frac = num.split(".", 1)
        digits = (whole + frac).lstrip("0")
        if not digits:
            return 1
        return len(digits)

    digits = num.lstrip("0")
    if not digits:
        return 1
    return len(digits)


def interval_from_sigfig(value: Decimal, significant_figures: int) -> Tuple[Decimal, Decimal]:
    if significant_figures <= 0:
        raise ValueError("significant_figures must be positive")

    if value.is_nan() or value.is_infinite():
        raise ValueError("non-finite decimal is not supported")

    if value == 0:
        quantum = Decimal(1).scaleb(-(significant_figures - 1))
    else:
        order = value.copy_abs().adjusted()
        quantum = Decimal(1).scaleb(order - significant_figures + 1)

    half = quantum / Decimal(2)
    return (value - half, value + half)


def make_quantified_claim(
    *,
    claim_id: str,
    magnitude: Magnitude,
    subject_id: str,
    actor_id: str,
    predicate: str,
    time_scope: str,
    modality: str,
    significant_figures: int,
    source_event_id: str,
) -> QuantifiedClaim:
    lb, ub = interval_from_sigfig(magnitude.value, significant_figures)
    return QuantifiedClaim(
        id=claim_id,
        magnitude_id=magnitude.id,
        subject_id=subject_id,
        actor_id=actor_id,
        predicate=predicate,
        time_scope=time_scope,
        modality=modality,
        significant_figures=significant_figures,
        lower_bound=lb,
        upper_bound=ub,
        source_event_id=source_event_id,
    )


def claims_overlap(a: QuantifiedClaim, b: QuantifiedClaim) -> bool:
    return a.lower_bound < b.upper_bound and b.lower_bound < a.upper_bound


def claims_conflict(a: QuantifiedClaim, b: QuantifiedClaim) -> bool:
    if a.subject_id != b.subject_id:
        return False
    if a.time_scope != b.time_scope:
        return False
    return not claims_overlap(a, b)


def classify_claim_relation(a: QuantifiedClaim, b: QuantifiedClaim) -> ClaimRelation:
    if a.subject_id != b.subject_id or a.time_scope != b.time_scope:
        return ClaimRelation.UNRELATED
    if a.magnitude_id == b.magnitude_id:
        return ClaimRelation.EXACT
    if claims_overlap(a, b):
        return ClaimRelation.COMPATIBLE
    return ClaimRelation.CONFLICT


def graduate_magnitude_anchor(usage: MagnitudeUsage, policy: GraduationPolicy = GraduationPolicy()) -> AnchorStatus:
    meets_recurrence = usage.recurrence_count >= policy.recurrence_threshold
    meets_cross_actor = usage.cross_actor_count >= policy.cross_actor_threshold
    meets_boundary = usage.boundary_usage_count >= policy.boundary_usage_threshold
    meets_priority_dimension = usage.dimension in policy.priority_dimensions

    if meets_recurrence and (meets_cross_actor or meets_boundary or meets_priority_dimension):
        return AnchorStatus.ANCHOR

    if usage.recurrence_count >= max(1, policy.recurrence_threshold - 1):
        return AnchorStatus.CANDIDATE

    return AnchorStatus.TRANSIENT


def authority_edges_for_quantified_claim(claim: QuantifiedClaim) -> List[AuthorityEdge]:
    claim_node = f"qclaim:{claim.id}"
    out = [
        AuthorityEdge(src=f"actor:{claim.actor_id}", predicate=claim.predicate, dst=claim_node),
        AuthorityEdge(src=claim_node, predicate="quantified_by", dst=claim.magnitude_id),
        AuthorityEdge(src=claim_node, predicate="about", dst=f"subject:{claim.subject_id}"),
        AuthorityEdge(src=claim_node, predicate="time_scope", dst=f"time:{claim.time_scope}"),
        AuthorityEdge(src=claim_node, predicate="source_event", dst=f"event:{claim.source_event_id}"),
    ]
    return out


def authority_edges_for_range_claim(claim: RangeClaim) -> List[AuthorityEdge]:
    node = f"rclaim:{claim.id}"
    return [
        AuthorityEdge(src=f"actor:{claim.actor_id}", predicate=claim.predicate, dst=node),
        AuthorityEdge(src=node, predicate="lower_bound", dst=claim.lower_magnitude_id),
        AuthorityEdge(src=node, predicate="upper_bound", dst=claim.upper_magnitude_id),
        AuthorityEdge(src=node, predicate="about", dst=f"subject:{claim.subject_id}"),
        AuthorityEdge(src=node, predicate="time_scope", dst=f"time:{claim.time_scope}"),
        AuthorityEdge(src=node, predicate="source_event", dst=f"event:{claim.source_event_id}"),
    ]


def authority_edges_for_ratio_claim(claim: RatioClaim) -> List[AuthorityEdge]:
    node = f"ratio:{claim.id}"
    return [
        AuthorityEdge(src=f"actor:{claim.actor_id}", predicate=claim.predicate, dst=node),
        AuthorityEdge(src=node, predicate="numerator", dst=claim.numerator_magnitude_id),
        AuthorityEdge(src=node, predicate="denominator", dst=claim.denominator_magnitude_id),
        AuthorityEdge(src=node, predicate="about", dst=f"subject:{claim.subject_id}"),
        AuthorityEdge(src=node, predicate="time_scope", dst=f"time:{claim.time_scope}"),
        AuthorityEdge(src=node, predicate="source_event", dst=f"event:{claim.source_event_id}"),
    ]


def parse_surface_magnitude(surface: str, default_unit: str = "") -> Optional[Magnitude]:
    raw = re.sub(r"\s+", " ", str(surface or "").strip())
    if not raw:
        return None

    s = raw.lower().replace(",", "")
    s = re.sub(r"\bper\s+cent\b", "percent", s)

    unit = normalize_unit(default_unit)
    if s.startswith("$"):
        unit = "usd"
        s = s[1:].strip()

    compact = re.match(r"^([+-]?\d+(?:\.\d+)?)([kmbt])$", s)
    if compact:
        value = Decimal(compact.group(1))
        exp = _SCALE_EXPONENT[compact.group(2)]
        return Magnitude(value=value.scaleb(exp), unit=unit, dimension="currency" if unit == "usd" else "unknown")

    m = re.match(
        r"^([+-]?\d+(?:\.\d+)?)(?:\s+(percent|usd|dollars?|thousand|million|billion|trillion))?$",
        s,
    )
    if not m:
        return None

    try:
        value = Decimal(m.group(1))
    except InvalidOperation:
        return None

    suffix = str(m.group(2) or "").strip().lower()
    if suffix in {"percent"}:
        unit = "percent"
    elif suffix in {"usd", "dollar", "dollars"}:
        unit = "usd"
    elif suffix in _SCALE_EXPONENT:
        value = value.scaleb(_SCALE_EXPONENT[suffix])

    return Magnitude(value=value, unit=unit, dimension="currency" if unit == "usd" else "unknown")


__all__ = [
    "AnchorStatus",
    "AuthorityEdge",
    "ClaimRelation",
    "GraduationPolicy",
    "Magnitude",
    "MagnitudeUsage",
    "NumericSurface",
    "QuantifiedClaim",
    "RangeClaim",
    "RatioClaim",
    "classify_claim_relation",
    "claims_conflict",
    "claims_overlap",
    "graduate_magnitude_anchor",
    "interval_from_sigfig",
    "magnitude_id",
    "make_quantified_claim",
    "normalize_decimal_text",
    "normalize_unit",
    "parse_surface_magnitude",
    "significant_figures_from_surface",
    "authority_edges_for_quantified_claim",
    "authority_edges_for_range_claim",
    "authority_edges_for_ratio_claim",
]
