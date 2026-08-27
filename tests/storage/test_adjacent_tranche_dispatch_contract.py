from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADJACENT = ROOT / "src" / "storage" / "postgres" / "numeric_adjacent_reconciliation.py"
MIGRATION_056 = ROOT / "database" / "postgres_migrations" / "056_numeric_pnf_adjacent_executor.sql"


def _source() -> str:
    return ADJACENT.read_text(encoding="utf-8")


def test_adjacent_tranche_preserves_existing_semantic_executor() -> None:
    source = _source()
    assert "execution.execute_numeric_pnf_adjacent_work" in source
    assert "execute_adjacent_lease_tranche" in source
    assert "WITH RECURSIVE" in source
    assert "input.ordinal = prior.ordinal + 1" in source
    assert "ORDER BY ordinal" in source


def test_adjacent_tranche_claim_and_dispatch_share_transaction() -> None:
    source = _source()
    drain_start = source.index("def drain_adjacent_reconciliation(")
    drain = source[drain_start:]
    assert "with connection.transaction():" in drain
    assert "claim_work_batch(" in drain
    assert "execute_adjacent_lease_tranche(cursor, leases)" in drain
    # The optimized normal path no longer opens a semantic transaction per pair.
    assert "for index, lease in enumerate(leases):" not in drain
    assert "release_unstarted_leases" not in source


def test_adjacent_tranche_receipt_declares_zero_pairwise_boundary_work() -> None:
    source = _source()
    assert "per_pair_client_round_trip_count=0" in source
    assert "per_pair_commit_count=0" in source
    assert "server_dispatch_statement_count=tranche_count" in source
    assert "authority_transaction_count=tranche_count" in source


def test_failed_tranche_is_atomic_not_partial_publication() -> None:
    source = _source()
    assert "failure rolls back the entire tranche" in source
    assert "publishes no successful prefix" in source
    assert "_fail_adjacent_lease" not in source


def test_existing_sql_executor_still_separates_evidence_from_resolution() -> None:
    migration = MIGRATION_056.read_text(encoding="utf-8")
    assert "semantic_pnf_adjacent_candidate_evidence" in migration
    assert "this executor never changes a demand's" in migration
    assert "resolved_target" in migration
    assert "adjacent reconciliation work fence changed at commit" in migration
