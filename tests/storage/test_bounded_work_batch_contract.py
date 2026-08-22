from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BATCH = ROOT / "src/storage/postgres/bounded_work_batch.py"
SENTENCE = ROOT / "src/policy/bounded_sentence_batch_leasing.py"
ADJACENT = ROOT / "src/storage/postgres/numeric_adjacent_reconciliation.py"
HOT_PATH = ROOT / "src/policy/closure_hot_path_execution.py"


def test_batch_claim_preserves_operation_order_and_skip_locked() -> None:
    source = BATCH.read_text(encoding="utf-8")

    assert "AND operation_id = %s" in source
    assert "ORDER BY priority, work_id" in source
    assert "FOR UPDATE SKIP LOCKED" in source
    assert "LIMIT %s" in source
    assert "lease_epoch=int(prior_epoch) + 1" in source
    assert "attempt_count = work.attempt_count + 1" in source


def test_batch_claim_uses_one_setwise_fenced_update() -> None:
    source = BATCH.read_text(encoding="utf-8")

    assert "unnest(%s::BIGINT[], %s::TEXT[], %s::BIGINT[])" in source
    assert "lease_token = leased.lease_token" in source
    assert "lease_epoch = leased.lease_epoch" in source
    assert "cursor.rowcount != len(leases)" in source


def test_unstarted_batch_members_are_returned_by_exact_fence() -> None:
    source = BATCH.read_text(encoding="utf-8")

    release = source.split("def release_unstarted_leases", 1)[1]
    assert "state_id = %s" in release
    assert "lease_token = abandoned.lease_token" in release
    assert "lease_epoch = abandoned.lease_epoch" in release
    assert "int(WorkState.READY)" in release
    assert "int(WorkState.LEASED)" in release


def test_sentence_batching_changes_only_lease_acquisition() -> None:
    source = SENTENCE.read_text(encoding="utf-8")

    assert "claim_work_batch(" in source
    assert "persist_sentence_closure_setwise(" in source
    assert "with connection.transaction():" in source
    assert "release_unstarted_leases(" in source
    assert "store.drain_sentence_closure = drain_sentence_closure" in source
    assert "streaming.drain_sentence_closure = drain_sentence_closure" in source


def test_adjacent_braids_keep_individual_execution_transactions() -> None:
    source = ADJACENT.read_text(encoding="utf-8")

    assert "claim_work_batch(" in source
    assert "for index, lease in enumerate(leases):" in source
    assert "execute_adjacent_lease(cursor, lease)" in source
    assert "release_unstarted_leases(cursor, leases[index + 1 :])" in source
    assert "does *not* assert" in source


def test_closure_hot_path_installs_sentence_batch_leasing() -> None:
    source = HOT_PATH.read_text(encoding="utf-8")

    assert "install_bounded_sentence_batch_leasing" in source
    assert "install_reusable_numeric_sentence_staging()" in source
    assert "install_bounded_sentence_batch_leasing()" in source
