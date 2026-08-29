from __future__ import annotations

from src.storage.postgres.numeric_sentence_evidence_admission import (
    EvidenceSupportCursor,
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


def test_unrelated_sql_is_unchanged() -> None:
    sql = "SELECT token_id FROM execution.semantic_parser_token WHERE token_id = %s"
    assert _rewrite_evidence_support_sql(sql) == sql


class _Cursor:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.rowcount = 0

    def execute(self, query: str, params=None):
        self.queries.append(query)
        return self


def test_cursor_facade_never_rewrites_parser_token_sql() -> None:
    cursor = _Cursor()
    wrapped = EvidenceSupportCursor(cursor)
    wrapped.execute("SELECT token_id FROM execution.semantic_parser_token")
    assert cursor.queries == ["SELECT token_id FROM execution.semantic_parser_token"]
