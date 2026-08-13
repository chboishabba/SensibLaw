from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_nullable_axis_digest_preserves_smallint_type() -> None:
    sql = (ROOT / "database/postgres_migrations/116_external_request_digest_smallint_fix.sql").read_text(
        encoding="utf-8"
    )
    assert "int2send(COALESCE(selected_axis_kind,0::smallint))" in sql
