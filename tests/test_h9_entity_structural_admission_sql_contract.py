from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M119 = (
    ROOT / "database/postgres_migrations/119_h9_entity_bearing_structural_admission.sql"
)
M120 = (
    ROOT / "database/postgres_migrations/120_h9_entity_admission_runtime_hardening.sql"
)
M121 = ROOT / "database/postgres_migrations/121_h9_entity_admission_invariant_guard.sql"
M122 = ROOT / "database/postgres_migrations/122_h9_provider_entity_occurrence_gate.sql"


def _sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function(sql: str, name: str) -> str:
    return sql.split(f"CREATE OR REPLACE FUNCTION execution.{name}", 1)[1].split(
        "$$;", 1
    )[0]


def test_entity_bearing_uses_structural_witnesses_not_propn_or_stopwords() -> None:
    sql = _sql(M119)
    view = sql.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_bearing_v1", 1
    )[1].split(";", 1)[0]
    assert "semantic_pnf_object_mention_support" in view
    assert "mention.mention_kind=1" in view
    assert "semantic_pnf_identity_projection" in view
    assert "semantic_pnf_mention_world_attachment" in view
    assert "PROPN" not in view
    assert "stopword" not in view.lower()
    assert "symbol_text" not in view
    assert "regexp" not in view.lower()


def test_provider_label_is_occurrence_anchor_not_demand_lexical_symbol() -> None:
    sql = _sql(M119)
    planner = _function(sql, "plan_numeric_pnf_external_demands_for_consumer")
    assert "need.label_symbol_id" in planner
    assert "need_row.label_symbol_id" in planner
    assert "demand.lexical_symbol_id" not in planner
    assert "external_need.lexical_symbol_id" not in planner


def test_multitoken_parser_entity_remains_entity_bearing_without_fake_phrase_label() -> (
    None
):
    sql = _sql(M119)
    anchors = sql.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_label_anchor_v1", 1
    )[1].split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_h9_preferred_entity_anchor_v1", 1
    )[0]
    assert "HAVING count(DISTINCT support.token_id)=1" in anchors
    assert "mention.mention_kind=1" in anchors
    assert "token.orth_symbol_id" in anchors
    assert "token.lemma_symbol_id" not in anchors


def test_property_requires_candidate_and_never_falls_back_to_discovery() -> None:
    sql = _sql(M119)
    admission = sql.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_h9_external_admission_v1", 1
    )[1].split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_h9_external_admission_summary_v1",
        1,
    )[0]
    planner = _function(sql, "plan_numeric_pnf_external_demands_for_consumer")
    assert "need_kind IN (2,3) AND NOT has_world_candidate" in admission
    property_branch = planner.split("ELSIF need_row.need_kind=2 THEN", 1)[1].split(
        "ELSE", 1
    )[0]
    assert "semantic_pnf_label_world_candidate" in property_branch
    assert "1::SMALLINT" not in property_branch


def test_identity_requires_occurrence_attached_world_candidate() -> None:
    sql = _sql(M120)
    assert "semantic_pnf_h9_attached_world_candidate_v1" in sql
    admission = sql.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_h9_external_admission_v1", 1
    )[1].split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_h9_external_admission_summary_v1",
        1,
    )[0]
    assert "has_attached_world_candidate" in admission
    assert "need_kind=3 AND NOT has_attached_world_candidate" in admission


def test_explicit_registration_has_no_unassigned_record_path() -> None:
    body = _function(_sql(M120), "record_numeric_pnf_consumer_external_need")
    assert "selected_anchor_object_id BIGINT" in body
    assert "selected_label_symbol_id BIGINT" in body
    assert "selected_anchor RECORD" not in body
    assert "external need requires entity-bearing structural label anchor" in body


def test_admission_observatory_keeps_rejection_reasons_numeric() -> None:
    sql = _sql(M119)
    assert "11 no source object" in sql
    assert "12 no entity witness" in sql
    assert "13 no exact label anchor" in sql
    assert "14 no represented world candidate" in sql
    summary = sql.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_h9_external_admission_summary_v1",
        1,
    )[1].split(";", 1)[0]
    assert "admission_reason" in summary
    assert "count(DISTINCT demand_id)" in summary


def test_active_need_global_invariant_is_machine_checkable() -> None:
    body = _function(_sql(M121), "verify_numeric_pnf_h9_external_admission")
    assert "need.active" in body
    assert "need.anchor_object_id IS NULL" in body
    assert "need.label_symbol_id IS NULL" in body
    assert "need.need_kind=2" in body
    assert "need.need_kind=3" in body
    assert "semantic_pnf_h9_entity_bearing_v1" in body
    assert "semantic_pnf_h9_attached_world_candidate_v1" in body


def test_reconciled_stale_requests_are_made_dormant_by_observer_refresh() -> None:
    sql = _sql(M121)
    assert "refresh_numeric_pnf_external_request_observer_state" in sql
    assert "refresh_numeric_pnf_external_request_cache_state" in sql


def test_local_identity_projection_cannot_authorize_provider_discovery() -> None:
    sql = _sql(M122)
    view = sql.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_h9_entity_bearing_v1", 1
    )[1].split(";", 1)[0]
    assert "mention.mention_kind=1" in view
    assert "semantic_pnf_mention_world_attachment" in view
    assert "semantic_pnf_identity_projection" not in view
    assert "semantic_pnf_consumer_external_need_origin" in sql
