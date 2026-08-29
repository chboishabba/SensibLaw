from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "database/postgres_migrations/214_direct_evidence_occurrence_provenance.sql"
).read_text(encoding="utf-8")
POLICY = (ROOT / "src/policy/producer_native_sentence_provenance.py").read_text(
    encoding="utf-8"
)
EVIDENCE = (ROOT / "src/storage/postgres/source_evidence_support.py").read_text(
    encoding="utf-8"
)


def test_direct_occurrence_provenance_has_an_evidence_native_carrier() -> None:
    assert "semantic_pnf_demand_evidence_occurrence_provenance" in MIGRATION
    assert "evidence_id BIGINT NOT NULL" in MIGRATION
    assert "semantic_pnf_demand_direct_evidence_target_occurrence_v1" in MIGRATION
    assert "semantic_pnf_demand_direct_evidence_occurrence_audit_v1" in MIGRATION


def test_direct_projection_uses_evidence_support_and_never_parser_tokens() -> None:
    direct_projection = POLICY.split("def _project_evidence_provenance", 1)[1].split(
        "def install_producer_native_sentence_provenance", 1
    )[0]
    assert "semantic_pnf_factor_evidence_support" in direct_projection
    assert "semantic_pnf_object_evidence_support" in direct_projection
    assert "semantic_source_token_evidence_annotation" in direct_projection
    assert "semantic_parser_token" not in direct_projection
    assert "HAVING count(*)=1" in direct_projection
    assert "numeric-factor-direct:" in direct_projection


def test_direct_mode_suppresses_legacy_parser_token_projection() -> None:
    assert "sensiblaw.direct_evidence_demand_provenance" in MIGRATION
    assert MIGRATION.count("RETURN NULL;") >= 2
    assert "evidence_native" in POLICY
    assert "_project_evidence_provenance(cursor)" in POLICY


def test_source_evidence_publishes_typed_lexical_coordinates_once() -> None:
    annotation_projection = EVIDENCE.split("def upsert_source_evidence_annotations", 1)[
        1
    ]
    assert "semantic_source_token_evidence_annotation" in annotation_projection
    assert "lemma_symbol_id" in annotation_projection
    assert "FROM execution.semantic_parser_token" not in annotation_projection
    assert "JOIN execution.semantic_parser_token" not in annotation_projection
