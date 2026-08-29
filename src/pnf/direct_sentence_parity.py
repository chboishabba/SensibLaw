"""Surrogate-independent observations for direct/reference sentence parity.

The numeric composer is intentionally allowed to use compact integer addresses while
solving a sentence.  Those addresses are transport identities, not semantic evidence.
Parity therefore resolves them back to typed symbol values and full source-evidence
digests before comparison.  Unknown ids fail closed rather than disappearing from the
observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.pnf.numeric_hyperfabric import SymbolKind
from src.pnf.numeric_operator_composition import NumericSentenceClosure


TypedSymbol = tuple[SymbolKind, str]


@dataclass(frozen=True, slots=True)
class StableObjectObservation:
    source_evidence_digest: bytes
    object_kind: TypedSymbol
    head: TypedSymbol
    information_gain: float
    representation_cost: float
    ambiguity_cost: float


@dataclass(frozen=True, slots=True)
class StableSlotObservation:
    role: TypedSymbol
    source_evidence_digest: bytes
    resolution_state: int
    required: bool


@dataclass(frozen=True, slots=True)
class StableFactorObservation:
    factor_type: TypedSymbol
    predicate: TypedSymbol
    modal_state: int
    temporal_state: int
    slots: tuple[StableSlotObservation, ...]
    support_evidence_digests: tuple[bytes, ...]
    residuals: tuple[TypedSymbol, ...]
    support_score: float


@dataclass(frozen=True, slots=True)
class StableDemandObservation:
    expected_target_kind: int
    expected_factor_type: TypedSymbol | None
    expected_object_kind: TypedSymbol | None
    lexical: TypedSymbol | None
    role: TypedSymbol | None
    residual_type: TypedSymbol
    recency_class: int
    max_candidates: int


@dataclass(frozen=True, slots=True)
class StableSentenceObservation:
    objects: tuple[StableObjectObservation, ...]
    factors: tuple[StableFactorObservation, ...]
    demands: tuple[StableDemandObservation, ...]


def _require_evidence(evidence_by_address: Mapping[int, bytes], address: int) -> bytes:
    try:
        digest = bytes(evidence_by_address[int(address)])
    except KeyError as exc:
        raise RuntimeError(f"sentence parity has no source evidence for address {address}") from exc
    if not digest:
        raise RuntimeError(f"sentence parity source evidence is empty for address {address}")
    return digest


def _require_symbol(symbol_by_id: Mapping[int, TypedSymbol], symbol_id: int) -> TypedSymbol:
    try:
        kind, text = symbol_by_id[int(symbol_id)]
    except KeyError as exc:
        raise RuntimeError(f"sentence parity has no typed symbol for id {symbol_id}") from exc
    if not isinstance(kind, SymbolKind) or not text:
        raise RuntimeError(f"sentence parity symbol {symbol_id} is not a stable typed value")
    return kind, str(text)


def _optional_symbol(
    symbol_by_id: Mapping[int, TypedSymbol], symbol_id: int | None
) -> TypedSymbol | None:
    return None if symbol_id is None else _require_symbol(symbol_by_id, symbol_id)


def observe_sentence_closure(
    closure: NumericSentenceClosure,
    *,
    evidence_by_address: Mapping[int, bytes],
    symbol_by_id: Mapping[int, TypedSymbol],
) -> StableSentenceObservation:
    """Erase database/local surrogates and expose only consumer-stable semantics."""

    objects = tuple(
        sorted(
            (
                StableObjectObservation(
                    source_evidence_digest=_require_evidence(
                        evidence_by_address, spec.source_token_id
                    ),
                    object_kind=_require_symbol(
                        symbol_by_id, spec.object_kind_symbol_id
                    ),
                    head=_require_symbol(symbol_by_id, spec.head_symbol_id),
                    information_gain=spec.information_gain,
                    representation_cost=spec.representation_cost,
                    ambiguity_cost=spec.ambiguity_cost,
                )
                for spec in closure.objects
            ),
            key=lambda row: (
                row.source_evidence_digest,
                int(row.object_kind[0]),
                row.object_kind[1],
                int(row.head[0]),
                row.head[1],
            ),
        )
    )
    factors = tuple(
        sorted(
            (
                StableFactorObservation(
                    factor_type=_require_symbol(
                        symbol_by_id, spec.factor_type_symbol_id
                    ),
                    predicate=_require_symbol(symbol_by_id, spec.predicate_symbol_id),
                    modal_state=spec.modal_state,
                    temporal_state=spec.temporal_state,
                    slots=tuple(
                        sorted(
                            (
                                StableSlotObservation(
                                    role=_require_symbol(
                                        symbol_by_id, slot.role_symbol_id
                                    ),
                                    source_evidence_digest=_require_evidence(
                                        evidence_by_address, slot.source_token_id
                                    ),
                                    resolution_state=int(slot.resolution_state),
                                    required=slot.required,
                                )
                                for slot in spec.slots
                            ),
                            key=lambda row: (
                                int(row.role[0]),
                                row.role[1],
                                row.source_evidence_digest,
                                row.resolution_state,
                                row.required,
                            ),
                        )
                    ),
                    support_evidence_digests=tuple(
                        sorted(
                            _require_evidence(evidence_by_address, token_id)
                            for token_id in spec.support_token_ids
                        )
                    ),
                    residuals=tuple(
                        sorted(
                            (
                                _require_symbol(symbol_by_id, residual_id)
                                for residual_id in spec.residual_symbol_ids
                            ),
                            key=lambda row: (int(row[0]), row[1]),
                        )
                    ),
                    support_score=spec.support_score,
                )
                for spec in closure.factors
            ),
            key=lambda row: (
                int(row.factor_type[0]),
                row.factor_type[1],
                int(row.predicate[0]),
                row.predicate[1],
                row.modal_state,
                row.temporal_state,
                row.slots,
                row.support_evidence_digests,
                row.residuals,
            ),
        )
    )
    demands = tuple(
        sorted(
            (
                StableDemandObservation(
                    expected_target_kind=int(spec.expected_target_kind),
                    expected_factor_type=_optional_symbol(
                        symbol_by_id, spec.expected_factor_type_symbol_id
                    ),
                    expected_object_kind=_optional_symbol(
                        symbol_by_id, spec.expected_object_kind_symbol_id
                    ),
                    lexical=_optional_symbol(symbol_by_id, spec.lexical_symbol_id),
                    role=_optional_symbol(symbol_by_id, spec.role_symbol_id),
                    residual_type=_require_symbol(
                        symbol_by_id, spec.residual_type_symbol_id
                    ),
                    recency_class=int(spec.recency_class),
                    max_candidates=spec.max_candidates,
                )
                for spec in closure.demands
            ),
            key=repr,
        )
    )
    return StableSentenceObservation(objects=objects, factors=factors, demands=demands)


def assert_sentence_parity(
    direct: StableSentenceObservation,
    reference: StableSentenceObservation,
) -> None:
    """Fail closed before publication if direct/reference semantics differ."""

    if direct != reference:
        raise RuntimeError(
            "direct/reference sentence parity mismatch; semantic publication is forbidden"
        )


__all__ = [
    "StableSentenceObservation",
    "TypedSymbol",
    "assert_sentence_parity",
    "observe_sentence_closure",
]
