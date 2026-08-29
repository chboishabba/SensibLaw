"""Publication boundary for DB-free sentence-local semantic closures.

Local composition owns semantic identity. Database ids are resolved only here,
and stable source evidence is scoped to the durable run/document. The existing
hyperfabric writer is reused while its legacy parser-token support writes are
redirected to evidence support.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable, Mapping
from uuid import uuid4

from src.pnf.numeric_hyperfabric import (
    ClosureState,
    RegionEdgeKind,
    RegionKind,
    WorkOperation,
    WorkState,
    numeric_digest,
)
from src.pnf.numeric_operator_composition import NumericSentenceClosure
from src.storage.postgres.numeric_hyperfabric_store import (
    WorkLease,
    _load_profile,
    _persist_sentence_closure,
)
from src.storage.postgres.numeric_symbol_store import intern_symbols, normalize_symbol
from src.storage.postgres.sentence_hyperfabric import LocalSentenceComposition


_OBJECT_TOKEN_SUPPORT = "execution.semantic_pnf_object_token_support"
_FACTOR_TOKEN_SUPPORT = "execution.semantic_pnf_factor_token_support"
_OBJECT_EVIDENCE_SUPPORT = "execution.semantic_pnf_object_evidence_support"
_FACTOR_EVIDENCE_SUPPORT = "execution.semantic_pnf_factor_evidence_support"


class _EvidenceSupportCursor:
    """Redirect only legacy token-support writes to stable evidence support."""

    def __init__(self, cursor: Any, evidence_id_by_local_token: Mapping[int, int]):
        self._cursor = cursor
        self._evidence_id_by_local_token = {
            int(token_id): int(evidence_id)
            for token_id, evidence_id in evidence_id_by_local_token.items()
        }

    def _evidence_id(self, local_token_id: int) -> int:
        try:
            return self._evidence_id_by_local_token[int(local_token_id)]
        except KeyError as error:
            raise RuntimeError(
                f"direct semantic support lost local token {int(local_token_id)}"
            ) from error

    def execute(self, query: Any, params: Any = None) -> Any:
        sql = str(query)
        if _OBJECT_TOKEN_SUPPORT in sql:
            if params is None or len(params) < 2:
                raise RuntimeError("object support write is missing parameters")
            object_id, local_token_id, *rest = params
            rewritten = sql.replace(_OBJECT_TOKEN_SUPPORT, _OBJECT_EVIDENCE_SUPPORT)
            return self._cursor.execute(
                rewritten.replace("token_id", "evidence_id"),
                (object_id, self._evidence_id(local_token_id), *rest),
            )
        return self._cursor.execute(query, params)

    def executemany(self, query: Any, params_seq: Iterable[Any]) -> Any:
        sql = str(query)
        if _FACTOR_TOKEN_SUPPORT in sql:
            rows = [
                (factor_id, self._evidence_id(local_token_id), ordinal)
                for factor_id, local_token_id, ordinal in params_seq
            ]
            rewritten = sql.replace(_FACTOR_TOKEN_SUPPORT, _FACTOR_EVIDENCE_SUPPORT)
            return self._cursor.executemany(
                rewritten.replace("token_id", "evidence_id"), rows
            )
        return self._cursor.executemany(query, params_seq)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


def _resolve_symbol_ids(
    cursor: Any, composition: LocalSentenceComposition
) -> dict[int, int]:
    values = [(binding.kind, binding.text) for binding in composition.symbol_bindings]
    db_by_value = intern_symbols(cursor, values)
    return {
        binding.local_ref: int(
            db_by_value[(binding.kind, normalize_symbol(binding.kind, binding.text))]
        )
        for binding in composition.symbol_bindings
    }


def _mapped(symbol_id: int | None, db_id_by_local: Mapping[int, int]) -> int | None:
    if symbol_id is None:
        return None
    try:
        return int(db_id_by_local[int(symbol_id)])
    except KeyError as error:
        raise RuntimeError(f"direct publication lost local symbol {int(symbol_id)}") from error


def reindex_closure_for_publication(
    closure: NumericSentenceClosure,
    *,
    db_symbol_id_by_local: Mapping[int, int],
) -> NumericSentenceClosure:
    """Translate relational symbol FKs while preserving semantic digest bytes."""

    objects = tuple(
        replace(
            row,
            object_kind_symbol_id=int(
                _mapped(row.object_kind_symbol_id, db_symbol_id_by_local)
            ),
            head_symbol_id=int(_mapped(row.head_symbol_id, db_symbol_id_by_local)),
        )
        for row in closure.objects
    )
    factors = tuple(
        replace(
            row,
            factor_type_symbol_id=int(
                _mapped(row.factor_type_symbol_id, db_symbol_id_by_local)
            ),
            predicate_symbol_id=int(
                _mapped(row.predicate_symbol_id, db_symbol_id_by_local)
            ),
            slots=tuple(
                replace(
                    slot,
                    role_symbol_id=int(
                        _mapped(slot.role_symbol_id, db_symbol_id_by_local)
                    ),
                )
                for slot in row.slots
            ),
            residual_symbol_ids=tuple(
                int(_mapped(symbol_id, db_symbol_id_by_local))
                for symbol_id in row.residual_symbol_ids
            ),
        )
        for row in closure.factors
    )
    demands = tuple(
        replace(
            row,
            expected_factor_type_symbol_id=_mapped(
                row.expected_factor_type_symbol_id, db_symbol_id_by_local
            ),
            expected_object_kind_symbol_id=_mapped(
                row.expected_object_kind_symbol_id, db_symbol_id_by_local
            ),
            lexical_symbol_id=_mapped(row.lexical_symbol_id, db_symbol_id_by_local),
            role_symbol_id=_mapped(row.role_symbol_id, db_symbol_id_by_local),
            residual_type_symbol_id=int(
                _mapped(row.residual_type_symbol_id, db_symbol_id_by_local)
            ),
        )
        for row in closure.demands
    )
    reindexed = NumericSentenceClosure(
        objects=objects,
        factors=factors,
        demands=demands,
        measure=closure.measure,
    )
    if tuple(row.object_digest for row in reindexed.objects) != tuple(
        row.object_digest for row in closure.objects
    ):
        raise AssertionError("object semantic digest changed during publication reindex")
    if tuple(row.factor_digest for row in reindexed.factors) != tuple(
        row.factor_digest for row in closure.factors
    ):
        raise AssertionError("factor semantic digest changed during publication reindex")
    if tuple(row.demand_digest for row in reindexed.demands) != tuple(
        row.demand_digest for row in closure.demands
    ):
        raise AssertionError("demand semantic digest changed during publication reindex")
    return reindexed


def _register_direct_region(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    composition: LocalSentenceComposition,
) -> tuple[int, int]:
    cursor.execute(
        """
        SELECT region_id
          FROM execution.semantic_pnf_region
         WHERE run_ref = %s
           AND document_ref = %s
           AND region_kind IN (3, 5, 6, 7, 8, 10)
           AND start_char <= %s
           AND end_char > %s
         ORDER BY
           CASE region_kind
               WHEN 3 THEN 1 WHEN 5 THEN 2 WHEN 6 THEN 3
               WHEN 7 THEN 4 WHEN 8 THEN 5 ELSE 6
           END,
           end_char - start_char
         LIMIT 1
        """,
        (run_ref, document_ref, composition.start_char, composition.start_char),
    )
    parent = cursor.fetchone()
    parent_region_id = int(parent[0]) if parent else None
    region_digest = numeric_digest(
        b"semantic_pnf_direct_sentence_region_v1",
        run_ref.encode("utf-8"),
        document_ref.encode("utf-8"),
        composition.sentence_digest,
        composition.start_char,
        composition.end_char,
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_pnf_region
            (region_digest, run_ref, document_ref, region_kind,
             start_char, end_char, sequence_no, parent_region_id,
             closure_state, authored_boundary)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
        ON CONFLICT (run_ref, document_ref, region_kind, start_char, end_char)
        DO UPDATE SET parent_region_id = COALESCE(
            execution.semantic_pnf_region.parent_region_id,
            EXCLUDED.parent_region_id
        )
        RETURNING region_id
        """,
        (
            region_digest,
            run_ref,
            document_ref,
            int(RegionKind.SENTENCE),
            composition.start_char,
            composition.end_char,
            composition.ordinal,
            parent_region_id,
            int(ClosureState.OPEN),
        ),
    )
    region_id = int(cursor.fetchone()[0])
    if parent_region_id is not None:
        cursor.execute(
            """
            INSERT INTO execution.semantic_pnf_region_edge
                (source_region_id, target_region_id, edge_kind, ordinal)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                region_id,
                parent_region_id,
                int(RegionEdgeKind.CONTAINS),
                composition.ordinal,
            ),
        )
    work_digest = numeric_digest(
        b"semantic_pnf_direct_sentence_work_v1",
        run_ref.encode("utf-8"),
        document_ref.encode("utf-8"),
        composition.sentence_digest,
        int(WorkOperation.SENTENCE_CLOSE),
    )
    cursor.execute(
        """
        INSERT INTO execution.semantic_pnf_work_item
            (work_digest, run_ref, document_ref, region_id,
             operation_id, state_id, priority)
        VALUES (%s, %s, %s, %s, %s, %s, 10)
        ON CONFLICT (region_id, operation_id) DO UPDATE SET
            state_id = CASE
                WHEN execution.semantic_pnf_work_item.state_id = %s THEN %s
                ELSE execution.semantic_pnf_work_item.state_id
            END
        RETURNING work_id
        """,
        (
            work_digest,
            run_ref,
            document_ref,
            region_id,
            int(WorkOperation.SENTENCE_CLOSE),
            int(WorkState.READY),
            int(WorkState.FAILED),
            int(WorkState.READY),
        ),
    )
    return region_id, int(cursor.fetchone()[0])


def _lease_direct_work(cursor: Any, *, work_id: int, region_id: int) -> WorkLease:
    token = uuid4().hex
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_work_item
           SET state_id = %s,
               lease_owner = 'semantic-direct-publication',
               lease_token = %s,
               lease_epoch = lease_epoch + 1,
               lease_expires_at = CURRENT_TIMESTAMP + INTERVAL '120 seconds',
               attempt_count = attempt_count + 1
         WHERE work_id = %s
           AND state_id IN (%s, %s)
        RETURNING lease_epoch
        """,
        (
            int(WorkState.LEASED),
            token,
            work_id,
            int(WorkState.READY),
            int(WorkState.FAILED),
        ),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("direct sentence work could not be leased")
    return WorkLease(
        work_id=work_id,
        region_id=region_id,
        operation=WorkOperation.SENTENCE_CLOSE,
        lease_token=token,
        lease_epoch=int(row[0]),
    )


def _upsert_source_evidence(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    composition: LocalSentenceComposition,
) -> dict[int, int]:
    result: dict[int, int] = {}
    for evidence in composition.source_evidence:
        cursor.execute(
            """
            INSERT INTO execution.semantic_pnf_source_evidence
                (evidence_digest, run_ref, document_ref, sentence_digest,
                 token_digest, start_char, end_char, evidence_kind)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
            ON CONFLICT (evidence_digest) DO UPDATE SET
                run_ref = EXCLUDED.run_ref,
                document_ref = EXCLUDED.document_ref
            RETURNING evidence_id
            """,
            (
                evidence.evidence_digest,
                run_ref,
                document_ref,
                composition.sentence_digest,
                evidence.token_digest,
                evidence.start_char,
                evidence.end_char,
            ),
        )
        result[evidence.local_token_ref] = int(cursor.fetchone()[0])
    return result


def publish_local_sentence(
    cursor: Any,
    *,
    run_ref: str,
    document_ref: str,
    composition: LocalSentenceComposition,
) -> int:
    """Publish one locally solved sentence without parser sentence/token rows."""

    db_symbols = _resolve_symbol_ids(cursor, composition)
    reindexed = reindex_closure_for_publication(
        composition.closure, db_symbol_id_by_local=db_symbols
    )
    evidence_ids = _upsert_source_evidence(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        composition=composition,
    )
    region_id, work_id = _register_direct_region(
        cursor,
        run_ref=run_ref,
        document_ref=document_ref,
        composition=composition,
    )
    lease = _lease_direct_work(cursor, work_id=work_id, region_id=region_id)
    profile = _load_profile(cursor)
    return _persist_sentence_closure(
        _EvidenceSupportCursor(cursor, evidence_ids),
        lease=lease,
        closure=reindexed,
        profile=profile,
    )


__all__ = ["publish_local_sentence", "reindex_closure_for_publication"]
