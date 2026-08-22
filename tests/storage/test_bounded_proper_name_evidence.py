from pathlib import Path


MIGRATION = Path("database/postgres_migrations/085_bounded_proper_name_evidence.sql")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_proper_name_fanout_is_bounded_before_mention_expansion() -> None:
    sql = _sql()
    assert "max_name_targets CONSTANT INTEGER := 16" in sql
    assert "family_target AS MATERIALIZED" in sql
    assert (
        "row_number() OVER (\n                   PARTITION BY person.family_lemma_symbol_id"
        in sql
    )
    assert "target.family_rank <= max_name_targets" in sql
    assert "semantic_pnf_proper_name_evidence_overflow" in sql


def test_person_membership_and_family_cardinality_are_shared_once() -> None:
    sql = _sql()
    assert "person_entity_member AS MATERIALIZED" in sql
    assert "count(*) OVER (PARTITION BY entity.entity_id) AS member_count" in sql
    assert "family_candidate_count" in sql
    assert "evidence_write AS" in sql
    assert "overflow_write AS" in sql
    # Candidate insertion and overflow receipt share one WITH carrier rather than
    # recomputing PERSON spans/families in a second statement.
    assert sql.count("person_entity_member AS MATERIALIZED") == 1
    assert sql.count("family_target AS MATERIALIZED") == 1


def test_embedded_person_name_tokens_are_not_standalone_expansion_sources() -> None:
    sql = _sql()
    assert "proper_name_mention AS MATERIALIZED" in sql
    assert "person_member_token AS MATERIALIZED" in sql
    assert "LEFT JOIN person_member_token AS member" in sql
    assert "WHERE member.token_id IS NULL" in sql


def test_bounded_ambiguity_remains_non_admissible_and_auditable() -> None:
    sql = _sql()
    assert "LEAST(256, family_candidate_count)::SMALLINT AS candidate_count" in sql
    assert "possible_target_count" in sql
    assert "retained_target_limit" in sql
    # Migration 085 produces parser evidence only; it must not create or admit
    # identity witnesses directly.
    assert "INSERT INTO execution.semantic_pnf_identity_witness\n" not in sql
    assert "INSERT INTO execution.semantic_pnf_identity_witness_admission\n" not in sql


def test_apposition_path_uses_precomputed_dependency_carrier() -> None:
    sql = _sql()
    assert "appos_token AS MATERIALIZED" in sql
    assert "FROM appos_token AS dependency" in sql
    # Avoid the old per-token correlated child scan used only to discover appos
    # heads in the anchor preparation path.
    assert "FROM doc_token AS child" not in sql
