from __future__ import annotations

from pathlib import Path

import pytest

from src.storage.postgres.consumer_sufficient_runtime_store import ConsumerSufficientRuntimeStore


ROOT = Path(__file__).resolve().parents[1]
M094 = ROOT / "database/postgres_migrations/094_context_scope_and_consumer_horizon_queue.sql"


def test_consumer_advance_uses_independent_queue_not_global_queue() -> None:
    sql = M094.read_text(encoding="utf-8")
    body = sql.split(
        "CREATE OR REPLACE FUNCTION execution.advance_numeric_pnf_horizon_work_for_consumer", 1
    )[1].split("$$;", 1)[0]
    assert "semantic_pnf_consumer_horizon_work_queue" in body
    assert "semantic_pnf_horizon_work_queue" not in body.replace(
        "semantic_pnf_consumer_horizon_work_queue", ""
    )
    assert "UPDATE execution.semantic_pnf_demand" not in body
    assert "resolved_target_id" not in body


def test_context_fit_is_scoped_by_numeric_mention_label() -> None:
    sql = M094.read_text(encoding="utf-8")
    view = sql.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_world_context_fit_v1", 1
    )[1].split("CREATE TABLE IF NOT EXISTS execution.semantic_pnf_consumer_horizon_work_queue", 1)[0]
    assert "token.orth_symbol_id" in view
    assert "token.lemma_symbol_id" in view
    assert "requirement.label_symbol_id IN" in view
    assert "JOIN requirement ON TRUE" not in view


def test_consumer_reverse_dependencies_are_sparse_source_keyed() -> None:
    sql = M094.read_text(encoding="utf-8")
    assert "semantic_pnf_consumer_reverse_dependency" in sql
    assert "source_kind" in sql
    assert "source_id" in sql
    assert "enqueue_numeric_pnf_affected_consumer_demands" in sql


def test_codec_v1_refuses_false_frequency_codebook_metadata() -> None:
    store = ConsumerSufficientRuntimeStore("postgresql://unused")
    with pytest.raises(ValueError, match="canonical SymbolId"):
        store.rebuild_numeric_observation_tape(
            run_ref="r",
            document_ref="d",
            codebook_revision=1,
        )
