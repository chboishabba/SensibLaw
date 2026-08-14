from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M135 = (ROOT / "database/postgres_migrations/135_secondary_entity_candidate_carrier.sql").read_text()
M136 = (ROOT / "database/postgres_migrations/136_h9_provider_entity_candidates.sql").read_text()
RUNNER = (ROOT / "scripts/run_secondary_provider_ner.py").read_text()
LOADER = (ROOT / "src/nlp/provider_ner.py").read_text()
REPORT = (ROOT / "scripts/report_h9_outgoing_entity_labels.py").read_text()


def test_secondary_pass_is_separate_append_only_evidence() -> None:
    assert "semantic_parser_secondary_entity_pass" in M135
    assert "semantic_parser_secondary_entity_span" in M135
    assert "DELETE FROM execution.semantic_parser_entity_span" not in M135
    assert "model_name TEXT NOT NULL" in M135
    assert "model_version TEXT NOT NULL" in M135


def test_secondary_spans_receive_same_provider_quality_gate() -> None:
    assert "semantic_parser_secondary_entity_span_quality_v1" in M135
    assert "geometry.verbal_token_count>0" in M135
    assert "geometry.token_count>16" in M135
    assert "semantic_parser_provider_entity_type" in M135
    assert "semantic_parser_entity_quality_terminal_pos" in M135
    assert "THEN 18" in M135


def test_provider_candidates_canonicalize_equal_spans_and_keep_support_provenance() -> None:
    assert "semantic_parser_provider_entity_candidate" in M135
    assert "semantic_parser_provider_entity_candidate_support" in M135
    assert "support_kind SMALLINT NOT NULL CHECK (support_kind IN (1,2))" in M135
    assert "primary_support_count" in M135
    assert "secondary_support_count" in M135


def test_support_receipts_do_not_depend_on_null_unique_semantics() -> None:
    assert "semantic_parser_provider_candidate_primary_support_uq" in M135
    assert "WHERE support_kind=1" in M135
    assert "semantic_parser_provider_candidate_secondary_support_uq" in M135
    assert "WHERE support_kind=2" in M135


def test_h9_consumes_canonical_candidates_and_preserves_ambiguity() -> None:
    assert "semantic_parser_provider_entity_candidate_current_v1" in M136
    assert "provider_entity_candidate_id AS entity_id" in M136
    assert "HAVING count(DISTINCT occurrence.entity_id)=1" in M136
    assert "semantic_pnf_identity_projection" not in M136


def test_secondary_loader_is_isolated_and_never_downloads_models() -> None:
    assert 'DEFAULT_PROVIDER_NER_MODEL = "en_core_web_trf"' in LOADER
    assert "SENSIBLAW_PROVIDER_NER_MODEL" in LOADER
    assert "spacy.load(requested)" in LOADER
    assert "download" not in "\n".join(
        line for line in LOADER.splitlines() if not line.lstrip().startswith("#")
    ).replace("downloading", "")
    assert "SENSIBLAW_SPACY_MODEL" not in LOADER


def test_secondary_runner_is_h9_bounded_and_provider_network_free() -> None:
    assert "semantic_pnf_h9_external_admission_v1" in RUNNER
    assert "admission.contract_id IS NOT NULL" in RUNNER
    assert "semantic_pnf_demand_strong_occurrence_support_v1" in RUNNER
    assert '"model_download_performed": False' in RUNNER
    assert '"provider_io_performed": False' in RUNNER
    assert "refresh_semantic_parser_provider_entity_candidates" in RUNNER


def test_report_exposes_primary_secondary_and_joint_support() -> None:
    assert "primary_support_count" in REPORT
    assert "secondary_support_count" in REPORT
    assert "jointly_supported" in REPORT
    assert '"provider_io_performed": False' in REPORT
