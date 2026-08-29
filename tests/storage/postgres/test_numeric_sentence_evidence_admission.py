from __future__ import annotations

import pytest

from src.storage.postgres.numeric_sentence_evidence_admission import (
    DirectProvenanceViolation,
    EvidenceSupportCursor,
    _collapse_bounded_executemany,
    _direct_authority_sql,
    _reuse_stage_setup_sql,
    _rewrite_evidence_support_sql,
)


def test_support_sql_rewrites_only_durable_support_insert_target() -> None:
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


def test_support_select_is_not_silently_rewritten() -> None:
    sql = """
        SELECT support.token_id
          FROM execution.semantic_pnf_factor_token_support AS support
         WHERE support.factor_id = %s
    """
    assert _rewrite_evidence_support_sql(sql) == sql
    with pytest.raises(DirectProvenanceViolation, match="semantic_pnf_factor_token_support"):
        _direct_authority_sql(sql)


def test_rewrite_helper_leaves_parser_sql_visible_to_authority_guard() -> None:
    sql = "SELECT token_id FROM execution.semantic_parser_token WHERE token_id = %s"
    assert _rewrite_evidence_support_sql(sql) == sql
    with pytest.raises(DirectProvenanceViolation, match="semantic_parser_token") as error:
        _direct_authority_sql(sql)
    assert "sql='SELECT token_id FROM execution.semantic_parser_token" in str(error.value)


class _Cursor:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.params: list[object] = []
        self.executemany_queries: list[str] = []
        self.rowcount = 0

    def execute(self, query: str, params=None):
        self.queries.append(query)
        self.params.append(params)
        return self

    def executemany(self, query: str, params_seq):
        self.executemany_queries.append(query)
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


def test_cursor_facade_rewrites_legacy_support_insert_without_leaking_relation() -> None:
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


def test_bounded_interface_executemany_collapses_to_one_statement() -> None:
    sql = """
        INSERT INTO execution.semantic_pnf_interface_export
            (interface_id, export_kind, target_kind, target_id,
             key_symbol_id, rank, promotion_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """
    batched = _collapse_bounded_executemany(
        sql,
        [(9, 1, 1, 10, 100, 0, 0.5), (9, 1, 1, 11, 101, 1, 0.4)],
    )
    assert batched is not None
    batched_sql, params = batched
    assert batched_sql.count("(%s, %s, %s, %s, %s, %s, %s)") == 2
    assert batched_sql.count("ON CONFLICT DO NOTHING") == 1
    assert params == (9, 1, 1, 10, 100, 0, 0.5, 9, 1, 1, 11, 101, 1, 0.4)


def test_cursor_facade_uses_one_execute_for_bounded_interface_rows() -> None:
    cursor = _Cursor()
    wrapped = EvidenceSupportCursor(cursor)
    sql = """
        INSERT INTO execution.semantic_pnf_interface_lookup
            (interface_id, key_kind, key_a, key_b, target_kind, target_id, rank)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """
    wrapped.executemany(sql, [(9, 1, 100, 0, 1, 10, 0), (9, 1, 101, 0, 1, 11, 1)])
    assert len(cursor.queries) == 1
    assert cursor.executemany_queries == []
    assert cursor.queries[0].count("(%s, %s, %s, %s, %s, %s, %s)") == 2


def test_non_interface_executemany_keeps_reference_shape() -> None:
    cursor = _Cursor()
    wrapped = EvidenceSupportCursor(cursor)
    sql = "INSERT INTO execution.some_other_table (a, b) VALUES (%s, %s)"
    wrapped.executemany(sql, [(1, 2), (3, 4)])
    assert cursor.queries == []
    assert cursor.executemany_queries == [sql]


def test_partition_cursor_defers_intermediate_ancestor_rebuild() -> None:
    cursor = _Cursor()
    wrapped = EvidenceSupportCursor(cursor, defer_interface_ancestors=True)
    result = wrapped.execute(
        "SELECT execution.rebuild_pnf_interface_ancestors(%s)",
        (123,),
    )
    assert result is wrapped
    assert cursor.queries == []


def test_standalone_cursor_keeps_exact_ancestor_rebuild() -> None:
    cursor = _Cursor()
    wrapped = EvidenceSupportCursor(cursor)
    sql = "SELECT execution.rebuild_pnf_interface_ancestors(%s)"
    wrapped.execute(sql, (123,))
    assert cursor.queries == [sql]
    assert cursor.params == [(123,)]


def test_stage_setup_is_created_once_then_reduced_to_truncate() -> None:
    sql = """
        CREATE TEMP TABLE IF NOT EXISTS tmp_numeric_sentence_object (ordinal INTEGER);
        CREATE TEMP TABLE IF NOT EXISTS tmp_numeric_sentence_factor (ordinal INTEGER);
        TRUNCATE TABLE tmp_numeric_sentence_object, tmp_numeric_sentence_factor;
    """
    first, created = _reuse_stage_setup_sql(sql, already_created=False)
    assert first == sql
    assert created is True
    second, created = _reuse_stage_setup_sql(sql, already_created=created)
    assert second.lstrip().lower().startswith("truncate table")
    assert "create temp table" not in second.lower()
    assert created is True


def test_partition_cursor_reuses_sentence_stage_ddl() -> None:
    cursor = _Cursor()
    wrapped = EvidenceSupportCursor(cursor, reuse_sentence_stages=True)
    sql = """
        CREATE TEMP TABLE IF NOT EXISTS tmp_numeric_sentence_object (ordinal INTEGER);
        TRUNCATE TABLE tmp_numeric_sentence_object;
    """
    wrapped.execute(sql)
    wrapped.execute(sql)
    assert "create temp table" in cursor.queries[0].lower()
    assert cursor.queries[1].lstrip().lower().startswith("truncate table")
    assert "create temp table" not in cursor.queries[1].lower()
