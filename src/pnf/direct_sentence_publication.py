"""Resolve direct sentence-local identities only at the durable publication boundary.

The direct compiler owns stable fibre-local symbol/evidence addresses. PostgreSQL
surrogate ids are storage locators and must not participate in sentence-local solve
identity. This adapter resolves the two address spaces in one durable transaction,
while preserving the semantic digests already produced by the direct composer.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from src.pnf.direct_sentence_compiler import DirectSentenceCompileReceipt
from src.pnf.numeric_hyperfabric import SymbolKind
from src.pnf.numeric_operator_composition import NumericSentenceClosure
from src.pnf.packed_sentence_fibre import PackedSentenceFibre
from src.storage.postgres.numeric_symbol_store import intern_symbols, normalize_symbol
from src.storage.postgres.source_evidence_support import upsert_source_evidence


@dataclass(frozen=True, slots=True)
class DirectPublicationReceipt:
    closure: NumericSentenceClosure
    local_symbol_to_database: tuple[tuple[int, int], ...]
    local_evidence_to_database: tuple[tuple[int, int], ...]
    parser_token_writes: int = 0


def _required(mapping: Mapping[int, int], value: int, *, kind: str) -> int:
    try:
        return int(mapping[int(value)])
    except KeyError as exc:
        raise RuntimeError(f"direct publication has no {kind} mapping for {value}") from exc


def remap_direct_closure(
    closure: NumericSentenceClosure,
    *,
    symbol_ids: Mapping[int, int],
    evidence_ids: Mapping[int, int],
) -> NumericSentenceClosure:
    """Replace local addresses with durable locators without changing semantic digests."""

    objects = tuple(
        replace(
            spec,
            source_token_id=_required(evidence_ids, spec.source_token_id, kind="evidence"),
            object_kind_symbol_id=_required(
                symbol_ids, spec.object_kind_symbol_id, kind="symbol"
            ),
            head_symbol_id=_required(symbol_ids, spec.head_symbol_id, kind="symbol"),
        )
        for spec in closure.objects
    )
    factors = tuple(
        replace(
            spec,
            factor_type_symbol_id=_required(
                symbol_ids, spec.factor_type_symbol_id, kind="symbol"
            ),
            predicate_symbol_id=_required(
                symbol_ids, spec.predicate_symbol_id, kind="symbol"
            ),
            slots=tuple(
                replace(
                    slot,
                    role_symbol_id=_required(
                        symbol_ids, slot.role_symbol_id, kind="symbol"
                    ),
                    source_token_id=_required(
                        evidence_ids, slot.source_token_id, kind="evidence"
                    ),
                )
                for slot in spec.slots
            ),
            support_token_ids=tuple(
                _required(evidence_ids, value, kind="evidence")
                for value in spec.support_token_ids
            ),
            residual_symbol_ids=tuple(
                _required(symbol_ids, value, kind="symbol")
                for value in spec.residual_symbol_ids
            ),
        )
        for spec in closure.factors
    )
    demands = tuple(
        replace(
            spec,
            expected_factor_type_symbol_id=(
                _required(symbol_ids, spec.expected_factor_type_symbol_id, kind="symbol")
                if spec.expected_factor_type_symbol_id is not None
                else None
            ),
            expected_object_kind_symbol_id=(
                _required(symbol_ids, spec.expected_object_kind_symbol_id, kind="symbol")
                if spec.expected_object_kind_symbol_id is not None
                else None
            ),
            lexical_symbol_id=(
                _required(symbol_ids, spec.lexical_symbol_id, kind="symbol")
                if spec.lexical_symbol_id is not None
                else None
            ),
            role_symbol_id=(
                _required(symbol_ids, spec.role_symbol_id, kind="symbol")
                if spec.role_symbol_id is not None
                else None
            ),
            residual_type_symbol_id=_required(
                symbol_ids, spec.residual_type_symbol_id, kind="symbol"
            ),
        )
        for spec in closure.demands
    )
    return replace(closure, objects=objects, factors=factors, demands=demands)


def resolve_direct_publication(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    fibre: PackedSentenceFibre,
    direct: DirectSentenceCompileReceipt,
) -> DirectPublicationReceipt:
    """Resolve only identities that survive from the local fibre into durable state.

    The evidence schema is migration-owned on canonical databases. Keeping DDL out of
    this per-sentence hot path avoids repeated catalog work during Gate-A publication.
    """

    database_symbols = intern_symbols(
        cursor,
        ((kind, text) for kind, text, _local_id in direct.symbol_ids),
    )
    local_symbol_to_database: dict[int, int] = {}
    for kind, text, local_id in direct.symbol_ids:
        normalized = normalize_symbol(SymbolKind(kind), text)
        try:
            database_id = int(database_symbols[(SymbolKind(kind), normalized)])
        except KeyError as exc:
            raise RuntimeError(
                f"durable symbol resolution lost {(SymbolKind(kind), normalized)!r}"
            ) from exc
        prior = local_symbol_to_database.setdefault(int(local_id), database_id)
        if prior != database_id:
            raise RuntimeError("one local symbol address resolved to multiple database ids")

    evidence_by_digest = upsert_source_evidence(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        fibres=(fibre,),
    )
    local_evidence_to_database: dict[int, int] = {}
    for local_id, digest in direct.source_evidence_ids:
        try:
            database_id = int(evidence_by_digest[bytes(digest)])
        except KeyError as exc:
            raise RuntimeError("durable evidence resolution lost a source digest") from exc
        prior = local_evidence_to_database.setdefault(int(local_id), database_id)
        if prior != database_id:
            raise RuntimeError("one local evidence address resolved to multiple database ids")

    resolved = remap_direct_closure(
        direct.closure,
        symbol_ids=local_symbol_to_database,
        evidence_ids=local_evidence_to_database,
    )
    return DirectPublicationReceipt(
        closure=resolved,
        local_symbol_to_database=tuple(sorted(local_symbol_to_database.items())),
        local_evidence_to_database=tuple(sorted(local_evidence_to_database.items())),
    )


__all__ = [
    "DirectPublicationReceipt",
    "remap_direct_closure",
    "resolve_direct_publication",
]
