from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.policy.carriers.canonical import canonical_sha256


TERNARY_ADMISSIBILITY_SCHEMA_VERSION = "sl.nat_ternary_admissibility.v0_2"

# Conventional three-valued logical/numeric presentations used by the bridge.
# Balanced Kleene-style ordering: false < unknown < true.
BALANCED_TRUTHINESS_TRITS = {
    "false": -1,
    "unknown": 0,
    "true": 1,
}
# Ordinary unsigned/unbalanced ternary uses digits 0, 1, 2.
UNBALANCED_TRUTHINESS_TRITS = {
    "false": 0,
    "unknown": 1,
    "true": 2,
}

# Wikibase does not itself assign these numeric truth values to snak types.
# These are explicit lossless presentation/interpretation codecs only.
EPISTEMIC_CENTRED_SNAK_TRITS = {
    "novalue": -1,
    "somevalue": 0,
    "value": 1,
}
ABSENCE_CENTRED_SNAK_TRITS = {
    "novalue": 0,
    "somevalue": -1,
    "value": 1,
}
# Conventional unsigned ternary digit labels for the same ordered three-symbol
# presentation.  This is 0/1/2, not 1/2/3.
UNBALANCED_SNAK_DIGITS = {
    "novalue": 0,
    "somevalue": 1,
    "value": 2,
}

ADMISSIBILITY_TRITS = {
    "blocked": -1,
    "open": 0,
    "admitted": 1,
}

BASE369_NINE_AXIS_ORDER = (
    "subject_identity",
    "transport",
    "native_family_coverage",
    "rank_visibility",
    "qualifier_constraints",
    "property_scope",
    "source_support",
    "authority",
    "semantic_correspondence",
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def encode_truthiness(value: str, *, balanced: bool = True) -> int:
    """Encode conventional three-valued truthiness.

    Balanced: false/unknown/true -> -1/0/+1.
    Unsigned: false/unknown/true -> 0/1/2.
    """

    key = _text(value).lower()
    table = BALANCED_TRUTHINESS_TRITS if balanced else UNBALANCED_TRUTHINESS_TRITS
    if key not in table:
        raise ValueError(f"unsupported three-valued truthiness value: {value}")
    return table[key]


def decode_truthiness(value: int, *, balanced: bool = True) -> str:
    table = BALANCED_TRUTHINESS_TRITS if balanced else UNBALANCED_TRUTHINESS_TRITS
    inverse = {digit: key for key, digit in table.items()}
    if value not in inverse:
        kind = "balanced trit" if balanced else "unsigned ternary digit"
        raise ValueError(f"not a conventional {kind}: {value}")
    return inverse[value]


def encode_snak_type(snak_type: str, *, orientation: str = "epistemic_centred") -> int:
    """Encode one native Wikibase snak type as a balanced trit.

    The result is an explicit representation/interpretation coordinate, not a
    claim that Wikibase defines the snak constructors as truth values.
    """

    key = _text(snak_type).lower()
    if orientation == "epistemic_centred":
        table = EPISTEMIC_CENTRED_SNAK_TRITS
    elif orientation == "absence_centred":
        table = ABSENCE_CENTRED_SNAK_TRITS
    else:
        raise ValueError(f"unsupported snak trit orientation: {orientation}")
    if key not in table:
        raise ValueError(f"unsupported Wikibase snak type: {snak_type}")
    return table[key]


def decode_snak_trit(trit: int, *, orientation: str = "epistemic_centred") -> str:
    if orientation == "epistemic_centred":
        table = EPISTEMIC_CENTRED_SNAK_TRITS
    elif orientation == "absence_centred":
        table = ABSENCE_CENTRED_SNAK_TRITS
    else:
        raise ValueError(f"unsupported snak trit orientation: {orientation}")
    inverse = {value: key for key, value in table.items()}
    if trit not in inverse:
        raise ValueError(f"not a balanced trit: {trit}")
    return inverse[trit]


def encode_snak_types(
    snak_types: Sequence[str], *, orientation: str = "epistemic_centred"
) -> list[int]:
    return [encode_snak_type(value, orientation=orientation) for value in snak_types]


def _admissibility_state(value: Any, *, blocked: bool = False) -> str:
    if blocked:
        return "blocked"
    return "admitted" if bool(value) else "open"


def build_nat_ternary_admissibility_projection(
    recomputation: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a Nat residual state onto an N-dimensional balanced-trit fibre.

    The full state remains N-dimensional. A selected nine-axis projection is
    additionally emitted in the exact axis order used to chart the state onto
    the existing Base369 T^9 / 19683 carrier. This does not assert Monster
    action/equivariance or identify Wikibase snak semantics with logical truth.
    """

    outcome = _text(recomputation.get("execution_outcome"))
    transport_blocked = outcome in {"engine_failed", "engine_unavailable"}

    axis_states = {
        "subject_identity": _admissibility_state(
            recomputation.get("qid_identity_resolved")
        ),
        "transport": _admissibility_state(
            outcome == "executed_with_output", blocked=transport_blocked
        ),
        "native_family_coverage": _admissibility_state(
            recomputation.get("coverage_coordinate_paid")
        ),
        "rank_visibility": _admissibility_state(
            recomputation.get("rank_visibility_evaluated")
        ),
        "qualifier_constraints": _admissibility_state(
            recomputation.get("qualifier_constraints_evaluated")
        ),
        "property_scope": _admissibility_state(
            recomputation.get("property_scope_evaluated")
        ),
        "property_derivability": _admissibility_state(
            recomputation.get("property_engine_derivability_evaluated")
        ),
        "source_support": _admissibility_state(
            recomputation.get("source_support_paid")
        ),
        "authority": _admissibility_state(
            recomputation.get("source_authority_paid")
        ),
        "semantic_correspondence": _admissibility_state(
            recomputation.get("semantic_correspondence_paid")
        ),
    }
    axis_trits = {axis: ADMISSIBILITY_TRITS[state] for axis, state in axis_states.items()}
    base369_nine_trits = [axis_trits[axis] for axis in BASE369_NINE_AXIS_ORDER]

    snak_types = recomputation.get("observed_native_snak_types")
    if not isinstance(snak_types, Sequence) or isinstance(
        snak_types, (str, bytes, bytearray)
    ):
        snak_types = []
    native_snak_types = sorted({_text(value) for value in snak_types if _text(value)})

    payload_without_ref = {
        "schema_version": TERNARY_ADMISSIBILITY_SCHEMA_VERSION,
        "source_recomputation_ref": _text(recomputation.get("recomputation_ref")),
        "axis_states": axis_states,
        "axis_trits": axis_trits,
        "dimension": len(axis_states),
        "base369_nine_axis_order": list(BASE369_NINE_AXIS_ORDER),
        "base369_nine_trits": base369_nine_trits,
        "base369_nominal_state_count": 3**9,
        "same_carrier_implies_monster_action": False,
        "conventional_balanced_truthiness": dict(BALANCED_TRUTHINESS_TRITS),
        "conventional_unbalanced_truthiness": dict(UNBALANCED_TRUTHINESS_TRITS),
        "snak_semantics_are_truth_values": False,
        "snak_truthiness_bridge_is_interpretive": True,
        "binary_zero_means_semantic_false": False,
        "native_snak_types": native_snak_types,
        "epistemic_centred_snak_trits": encode_snak_types(native_snak_types),
        "absence_centred_snak_trits": encode_snak_types(
            native_snak_types, orientation="absence_centred"
        ),
        "unbalanced_snak_digits": [UNBALANCED_SNAK_DIGITS[value] for value in native_snak_types],
    }
    payload = dict(payload_without_ref)
    payload["projection_ref"] = "nat-ternary-admissibility:" + canonical_sha256(
        payload_without_ref
    )
    return payload


__all__ = [
    "ABSENCE_CENTRED_SNAK_TRITS",
    "ADMISSIBILITY_TRITS",
    "BALANCED_TRUTHINESS_TRITS",
    "BASE369_NINE_AXIS_ORDER",
    "EPISTEMIC_CENTRED_SNAK_TRITS",
    "TERNARY_ADMISSIBILITY_SCHEMA_VERSION",
    "UNBALANCED_SNAK_DIGITS",
    "UNBALANCED_TRUTHINESS_TRITS",
    "build_nat_ternary_admissibility_projection",
    "decode_snak_trit",
    "decode_truthiness",
    "encode_snak_type",
    "encode_snak_types",
    "encode_truthiness",
]
