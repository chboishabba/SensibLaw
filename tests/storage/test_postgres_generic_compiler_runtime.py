from pathlib import Path

import pytest

from src.storage.postgres.token_codec import (
    CorpusCodec,
    decode_delta_sequence,
    decode_uvarints,
    encode_delta_sequence,
    encode_uint_sequence,
    encode_uvarint,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/postgres_migrations/006_generic_compiler_runtime.sql"
FACTOR_REVISION_MIGRATION = (
    ROOT / "database/postgres_migrations/007_factor_revision_identity.sql"
)
CLI = ROOT / "scripts/compile_corpus.py"


@pytest.mark.parametrize("value", [0, 1, 127, 128, 255, 16_384, 2**31 - 1])
def test_unsigned_varint_round_trip(value: int) -> None:
    assert decode_uvarints(encode_uvarint(value)) == (value,)


def test_sequence_and_delta_round_trip() -> None:
    values = (0, 1, 3, 127, 128, 10_000)
    assert decode_uvarints(encode_uint_sequence(values)) == values
    offsets = (0, 3, 4, 9, 20, 21)
    assert decode_delta_sequence(encode_delta_sequence(offsets)) == offsets


def test_frequency_ranked_codec_preserves_logical_ids() -> None:
    logical_ids = (91, 4, 91, 7, 91, 4, 8000)
    codec = CorpusCodec.from_lexeme_ids(logical_ids)
    assert codec.logical_to_symbol[91] == 0
    assert codec.logical_to_symbol[4] == 1
    assert codec.decode(codec.encode(logical_ids)) == logical_ids


def test_codec_rejects_unknown_logical_id() -> None:
    codec = CorpusCodec.from_lexeme_ids((1, 2, 2))
    with pytest.raises(ValueError, match="absent from codec"):
        codec.encode((1, 3))


def test_postgres_migration_is_generic_and_compression_aware() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    for schema in (
        "corpus",
        "language",
        "algebra",
        "pnf",
        "evidence",
        "resolution",
        "execution",
        "governance",
    ):
        assert f"CREATE SCHEMA IF NOT EXISTS {schema};" in sql
    assert "lexeme_id integer GENERATED ALWAYS AS IDENTITY" in sql
    assert "language.codec_symbol" in sql
    assert "language.token_stream_chunk" in sql
    assert "encoded_symbols bytea" in sql
    assert "resolution.v_unresolved_demand" in sql
    assert "pnf.v_document_pnf" in sql
    assert "worldmonitor" not in sql.casefold()
    assert "wikidata" not in sql.casefold()
    assert "gwb" not in sql.casefold()
    assert "au_mini" not in sql.casefold()


def test_factor_identity_is_separate_from_immutable_revisions() -> None:
    sql = FACTOR_REVISION_MIGRATION.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS algebra.factor_revision" in sql
    assert "algebra.factor_revision_alternative" in sql
    assert "pnf.graph_factor_revision" in sql
    assert "prior_factor_revision_ref" in sql
    assert "resulting_factor_revision_ref" in sql


def test_cli_defaults_to_postgres_and_json_is_explicit_legacy_export() -> None:
    source = CLI.read_text(encoding="utf-8")
    assert "--database-url" in source
    assert "DATABASE_URL" in source
    assert "--emit-legacy-json" in source
    assert "compile_directory_postgres" in source
    assert "--output" not in source
