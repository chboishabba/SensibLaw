from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECTION = ROOT / "src/storage/postgres/spacy_numeric_projection.py"


def _head_lookup_source() -> str:
    source = PROJECTION.read_text(encoding="utf-8")
    return source.split("raw_token_refs =", 1)[1].split(
        "cursor.executemany(", 1
    )[0]


def test_numeric_head_lookup_is_bounded_by_current_raw_token_refs() -> None:
    lookup = _head_lookup_source()

    assert "token_ref = ANY(%s)" in lookup
    assert "raw_token_refs" in lookup
    assert "partition.run_ref" in lookup
    assert "partition.document_ref" in lookup


def test_numeric_head_lookup_does_not_reload_whole_document_token_carrier() -> None:
    lookup = _head_lookup_source()

    # The run/document predicates remain defensive identity checks, but the
    # primary selectivity must come from the exact current token-ref set.
    where_clause = lookup.split("WHERE", 1)[1]
    assert where_clause.index("token_ref = ANY(%s)") < where_clause.index("run_ref = %s")
    assert "token_rows_by_span" not in lookup
