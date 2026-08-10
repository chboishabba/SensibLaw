from pathlib import Path


M077 = Path("database/postgres_migrations/077_identity_evidence_production_v1.sql")
M078 = Path("database/postgres_migrations/078_identity_evidence_parser_sentence_alignment.sql")
M079 = Path("database/postgres_migrations/079_identity_evidence_admission_policy.sql")
M080 = Path("database/postgres_migrations/080_identity_evidence_witness_provenance.sql")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_parser_evidence_has_explicit_candidate_layer() -> None:
    source = _text(M077)
    assert "semantic_pnf_identity_evidence_candidate" in source
    assert "semantic_pnf_parser_object_anchor" in source
    assert "refresh_numeric_pnf_parser_identity_evidence" in source
    assert "admit_numeric_pnf_parser_identity_evidence" in source
    assert "refresh_numeric_pnf_semantic_derivations" in source


def test_apposition_is_dependency_grounded_not_coscope_grounded() -> None:
    source = _text(M078).casefold()
    assert "dependency.symbol_text = 'appos'" in source
    assert "head_token_id" in source
    assert "parser-appos:" in source
    assert "paragraph" not in source
    assert "semantic_pnf_global_lookup" not in source


def test_title_role_closure_requires_person_apposition_evidence() -> None:
    source = _text(M078)
    assert "source_is_person <> target_is_person" in source
    assert "THEN 4 ELSE 2" in source
    assert "entity_type.symbol_text = 'PERSON'" in source


def test_proper_name_expansion_preserves_ambiguity() -> None:
    source = _text(M078)
    assert "family_cardinality" in source
    assert "count(DISTINCT parser_entity_id)::SMALLINT AS candidate_count" in source
    policy = _text(M080)
    assert "candidate.witness_kind = 3" in policy
    assert "corroborating.witness_kind IN (2, 4, 5, 6, 8)" in policy


def test_name_expansion_cannot_bootstrap_identity_from_uniqueness_alone() -> None:
    policy = _text(M080)
    assert "candidate.witness_kind IN (2, 4, 6)" in policy
    assert "candidate.witness_kind = 3" in policy
    assert "corroborating_admission.admission_state = 2" in policy


def test_explicit_alias_requires_lexical_relation_cue() -> None:
    source = _text(M078).casefold()
    assert "('aka', 'a.k.a.', 'alias')" in source
    assert "lower(cue_text.symbol_text) = 'known'" in source
    assert "lower(as_text.symbol_text) = 'as'" in source
    assert "explicit-alias:" in source


def test_parser_witness_retraction_is_provenance_scoped() -> None:
    source = _text(M080)
    assert "semantic_pnf_identity_evidence_witness" in source
    assert "candidate.candidate_id = provenance.candidate_id" in source
    assert "admission.witness_id = provenance.witness_id" in source
    assert "witness_kind IN (1, 2, 3, 4, 6)" not in source.split(
        "-- Retract only witnesses", 1
    )[1].split("INSERT INTO execution.semantic_pnf_canonical_entity", 1)[0]


def test_anaphora_remains_typed_demand_authority() -> None:
    source = _text(M077)
    wrapper = source.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_semantic_derivations",
        1,
    )[1]
    assert "refresh_numeric_pnf_identity_witnesses" in wrapper
    assert "refresh_numeric_pnf_parser_identity_evidence" in wrapper
    assert "admit_numeric_pnf_parser_identity_evidence" in wrapper


def test_no_json_or_similarity_authority_is_introduced() -> None:
    folded = "\n".join(_text(path).casefold() for path in (M077, M078, M079, M080))
    assert "jsonb" not in folded
    assert "::json" not in folded
    assert "similarity(" not in folded
