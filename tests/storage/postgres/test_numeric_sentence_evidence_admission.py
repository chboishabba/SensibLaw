from __future__ import annotations

import pytest

from src.storage.postgres.numeric_sentence_evidence_admission import (
    DirectProvenanceViolation,
    EvidenceSupportCursor,
    _direct_authority_sql,
    _rewrite_evidence_support_sql,
)


def test_support_sql_rewrites_only_durable_support_carrier() -> None:
    object_sql = """
        INSERT INTO execution.semantic_pnf_object_token_support
            (object_id, token_id, ordinal)
        SELECT object.object_id, stage.source_token_id, 0
          FROM tmp_numeric_sentence_object AS stage
    """
    factor_sql = """
        INSERT INTO execution.semantic_pnf_factor_token_support
            (factor_id, token_id, ordinal)
        SELECT factor.factor_id, support.token_id, support.support_ordinal
          FROM tmp_numeric_sentence_factor_support AS support
    """
    rewritten_object = _rewrite_evidence_support_sql(object_sql)
    rewritten_factor = _rewrite_evidence_support_sql(factor_sql)

    assert "semantic_pnf_object_evidence_support" in rewritten_object
    assert "(object_id, evidence_id, ordinal)" in rewritten_object
    assert "stage.source_token_id" in rewritten_object
    assert "semantic_pnf_factor_evidence_support" in rewritten_factor
    assert "(factor_id, evidence_id, ordinal)" in rewritten_factor
    assert "support.token_id" in rewritten_factor
    assert "semantic_pnf_object_token_support" not in rewritten_object
    assert "semantic_pnf_factor_token_support" not in rewritten_factor


def test_rewrite_helper_remains_mechanical_but_direct_authority_fails_closed() -> None:
    sql = "SELECT token_id FROM execution.semantic_parser_token WHERE token_id = %s"
    assert _rewrite_evidence_support_sql(sql) == sql
    with pytest.raises(DirectProvenanceViolation, match="semantic_parser_token"):
        _direct_authority_sql(sql)


class _Cursor:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.rowcount = 0

    def execute(self, query: str, params=None):
        self.queries.append(query)
        return self


def test_cursor_facade_rejects_parser_token_sql_before_database_crossing() -> None:
    cursor = _Cursor()
    wrapped = EvidenceSupportCursor(cursor)
    with pytest.raises(DirectProvenanceViolation, match="semantic_parser_token"):
        wrapped.execute("SELECT token_id FROM execution.semantic_parser_token")
    assert cursor.queries == []


def test_cursor_facade_keeps_demand_scheduling_sql_authoritative() -> None:
    cursor = _Cursor()
    wrapped = EvidenceSupportCursor(cursor)
    demand_sql = """
        INSERT INTO execution.semantic_pnf_demand
            (demand_digest, source_region_id, state)
        VALUES (%s, %s, 1)
        ON CONFLICT (demand_digest) DO UPDATE SET state = 1
    """
    wrapped.execute(demand_sql, (b"digest", 7))
    assert cursor.queries == [demand_sql]


def test_cursor_facade_rewrites_legacy_support_without_leaking_token_relation() -> None:
    cursor = _Cursor()
    wrapped = EvidenceSupportCursor(cursor)
    wrapped.execute(
        "INSERT INTO execution.semantic_pnf_object_token_support "
        "(object_id, token_id, ordinal) VALUES (%s, %s, %s)",
        (1, 2, 0),
    )
    assert len(cursor.queries) == 1
    assert "semantic_pnf_object_evidence_support" in cursor.queries[0]
    assert "(object_id, evidence_id, ordinal)" in cursor.queries[0]
    assert "semantic_pnf_object_token_support" not in cursor.queries[0]
