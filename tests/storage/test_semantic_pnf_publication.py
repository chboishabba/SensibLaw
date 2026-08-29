from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.pnf.numeric_hyperfabric import (
    PromotionEvidence,
    RecencyClass,
    RegionMeasure,
    ResolutionState,
    TargetKind,
)
from src.pnf.numeric_operator_composition import (
    NumericDemandSpec,
    NumericFactorSpec,
    NumericObjectSpec,
    NumericSentenceClosure,
    NumericSlotSpec,
)
from src.storage.postgres.semantic_pnf_publication import (
    _EvidenceSupportCursor,
    reindex_closure_for_publication,
)


def _closure() -> NumericSentenceClosure:
    evidence = PromotionEvidence(
        information_gain=1.0,
        representation_cost=0.25,
        ambiguity_cost=0.0,
    )
    return NumericSentenceClosure(
        objects=(
            NumericObjectSpec(
                object_digest=b"o" * 32,
                source_token_id=101,
                object_kind_symbol_id=201,
                head_symbol_id=202,
                information_gain=1.0,
                representation_cost=0.25,
                ambiguity_cost=0.0,
                promotion_evidence=evidence,
            ),
        ),
        factors=(
            NumericFactorSpec(
                factor_digest=b"f" * 32,
                factor_type_symbol_id=203,
                predicate_symbol_id=204,
                modal_state=1,
                temporal_state=0,
                slots=(
                    NumericSlotSpec(
                        role_symbol_id=205,
                        source_token_id=101,
                        resolution_state=ResolutionState.RESOLVED,
                    ),
                ),
                support_token_ids=(101,),
                residual_symbol_ids=(206,),
                support_score=1.0,
            ),
        ),
        demands=(
            NumericDemandSpec(
                demand_digest=b"d" * 32,
                expected_target_kind=TargetKind.OBJECT,
                expected_factor_type_symbol_id=203,
                expected_object_kind_symbol_id=201,
                lexical_symbol_id=202,
                role_symbol_id=205,
                residual_type_symbol_id=206,
                recency_class=RecencyClass.SAME_REGION,
            ),
        ),
        measure=RegionMeasure(node_count=2, edge_count=1),
    )


def test_publication_reindex_changes_only_relational_symbol_ids() -> None:
    original = _closure()
    mapping = {local: local + 1000 for local in range(201, 207)}
    published = reindex_closure_for_publication(
        original,
        db_symbol_id_by_local=mapping,
    )

    assert published.objects[0].object_digest == original.objects[0].object_digest
    assert published.factors[0].factor_digest == original.factors[0].factor_digest
    assert published.demands[0].demand_digest == original.demands[0].demand_digest
    assert published.objects[0].source_token_id == 101
    assert published.objects[0].object_kind_symbol_id == 1201
    assert published.objects[0].head_symbol_id == 1202
    assert published.factors[0].factor_type_symbol_id == 1203
    assert published.factors[0].predicate_symbol_id == 1204
    assert published.factors[0].slots[0].role_symbol_id == 1205
    assert published.factors[0].slots[0].source_token_id == 101
    assert published.factors[0].support_token_ids == (101,)
    assert published.factors[0].residual_symbol_ids == (1206,)
    assert published.demands[0].residual_type_symbol_id == 1206


class RecordingCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def execute(self, query, params=None):
        self.calls.append((str(query), params))
        return self

    def executemany(self, query, params_seq):
        self.calls.append((str(query), tuple(params_seq)))
        return self


def test_evidence_cursor_redirects_object_and_factor_support_only() -> None:
    raw = RecordingCursor()
    cursor = _EvidenceSupportCursor(raw, {101: 9001, 102: 9002})

    cursor.execute(
        "INSERT INTO execution.semantic_pnf_object_token_support "
        "(object_id, token_id, ordinal) VALUES (%s, %s, 0)",
        (7, 101),
    )
    cursor.executemany(
        "INSERT INTO execution.semantic_pnf_factor_token_support "
        "(factor_id, token_id, ordinal) VALUES (%s, %s, %s)",
        [(8, 101, 0), (8, 102, 1)],
    )
    cursor.execute("SELECT 1", ())

    object_sql, object_params = raw.calls[0]
    factor_sql, factor_params = raw.calls[1]
    assert "semantic_pnf_object_evidence_support" in object_sql
    assert "semantic_pnf_factor_evidence_support" in factor_sql
    assert "semantic_parser_token" not in object_sql + factor_sql
    assert "token_support" not in object_sql + factor_sql
    assert object_params == (7, 9001)
    assert factor_params == ((8, 9001, 0), (8, 9002, 1))
    assert raw.calls[2] == ("SELECT 1", ())


def test_evidence_cursor_fails_closed_on_unmapped_local_token() -> None:
    cursor = _EvidenceSupportCursor(RecordingCursor(), {})
    with pytest.raises(RuntimeError, match="lost local token 101"):
        cursor.execute(
            "INSERT INTO execution.semantic_pnf_object_token_support "
            "(object_id, token_id, ordinal) VALUES (%s, %s, 0)",
            (7, 101),
        )
