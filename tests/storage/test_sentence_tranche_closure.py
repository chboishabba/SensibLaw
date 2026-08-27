from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FACADE = ROOT / "src" / "storage" / "postgres" / "numeric_sentence_tranche_closure.py"
TRANCHE = ROOT / "src" / "storage" / "postgres" / "numeric_sentence_tranche_closure_setwise.py"
ADMISSION = ROOT / "src" / "storage" / "postgres" / "numeric_sentence_tranche_admission.py"
STREAMING = ROOT / "src" / "storage" / "postgres" / "streaming_spacy_execution.py"


def _tranche() -> str:
    return TRANCHE.read_text(encoding="utf-8")


def _admission() -> str:
    return ADMISSION.read_text(encoding="utf-8")


def test_compatibility_surface_promotes_e0b_scheduler() -> None:
    source = FACADE.read_text(encoding="utf-8")
    assert "numeric_sentence_tranche_closure_setwise" in source
    assert "close_sentence_tranche_setwise as close_sentence_tranche" in source
    assert "drain_sentence_closure_tranches" in source


def test_tranche_claims_sentence_work_setwise() -> None:
    source = _tranche()
    assert "WITH picked AS" in source
    assert "FOR UPDATE SKIP LOCKED" in source
    assert "LIMIT %s" in source
    assert "UPDATE execution.semantic_pnf_work_item AS work" in source
    assert "RETURNING work.work_id, work.region_id, work.lease_epoch" in source
    assert "lease_epoch = work.lease_epoch + 1" in source


def test_tranche_loads_all_sentence_tokens_in_one_query() -> None:
    source = _tranche()
    assert "link.region_id = ANY(%s)" in source
    assert "ORDER BY link.region_id, token.local_token_ordinal" in source
    assert "_load_sentence_tokens_tranche" in source
    assert "_load_sentence_tokens(" not in source


def test_tranche_reuses_semantic_producer_and_tranche_authority_writer() -> None:
    source = _tranche()
    assert "compose_numeric_sentence(" in source
    assert "persist_sentence_tranche_setwise(" in source
    assert "persist_sentence_closure_setwise(" not in source
    assert "for index, (lease, closure)" not in source


def test_tranche_has_one_outer_transaction_and_no_per_sentence_commit() -> None:
    source = _tranche()
    close_start = source.index("def close_sentence_tranche_setwise(")
    drain_start = source.index("def drain_sentence_closure_tranches(")
    close = source[close_start:drain_start]
    assert close.count("with connection.transaction():") == 1
    assert "persist_sentence_tranche_setwise(" in close
    assert "per_sentence_claim_round_trip_count=0" in source
    assert "per_sentence_transaction_count=0" in source


def test_tranche_is_atomic_on_failure_by_using_transaction_scope() -> None:
    source = _tranche()
    assert "with connection.transaction():" in source
    assert "persist_sentence_tranche_setwise(" in source
    assert "last_error_code" not in source
    assert "connection.commit(" not in source


def test_tranche_authority_uses_region_keyed_fixed_stages() -> None:
    source = _admission()
    assert "tmp_numeric_sentence_tranche_object" in source
    assert "tmp_numeric_sentence_tranche_factor" in source
    assert "tmp_numeric_sentence_tranche_demand" in source
    assert "PRIMARY KEY (region_id, ordinal)" in source
    assert "with cursor.copy(" in source
    assert '_OBJECT_STAGE = "tmp_numeric_sentence_tranche_object"' in source
    assert '_FACTOR_STAGE = "tmp_numeric_sentence_tranche_factor"' in source
    assert '_DEMAND_STAGE = "tmp_numeric_sentence_tranche_demand"' in source


def test_tranche_authority_preserves_exact_per_sentence_interface_digest() -> None:
    source = _admission()
    assert "interface_digest = numeric_digest(" in source
    assert "promoted.get(lease.region_id, [])" in source
    assert "factors.get(lease.region_id, [])" in source
    assert "demands.get(lease.region_id, [])" in source
    assert "PARTITION BY stage.region_id" in source


def test_tranche_authority_has_no_per_sentence_family_loop() -> None:
    source = _admission()
    persist = source[source.index("def persist_sentence_tranche_setwise(") :]
    assert "persist_sentence_closure_setwise" not in persist
    assert "for lease, closure in admissions:" not in persist
    assert "per_sentence_stage_create_count=0" in source
    assert "per_sentence_family_statement_count=0" in source


def test_tranche_authority_completes_work_setwise_with_exact_fence() -> None:
    source = _admission()
    assert "UPDATE execution.semantic_pnf_work_item AS work" in source
    assert "work.lease_token = stage.lease_token" in source
    assert "work.lease_epoch = stage.lease_epoch" in source
    assert "cursor.rowcount != len(admissions)" in source


def test_streaming_pipeline_uses_tranche_closure_everywhere() -> None:
    source = STREAMING.read_text(encoding="utf-8")
    assert "from src.storage.postgres.numeric_sentence_tranche_closure import (" in source
    assert source.count("drain_sentence_closure_tranches(") >= 3
    assert "drain_sentence_closure," not in source
    assert "drain_sentence_closure(" not in source
    assert "closure_receipt.sentence_count" in source


def test_coordinator_uses_one_large_bounded_tranche() -> None:
    source = STREAMING.read_text(encoding="utf-8")
    start = source.index("def _drain_remaining_sentence_closure")
    end = source.index("def _drain_remaining_adjacent_reconciliation", start)
    coordinator = source[start:end]
    assert "limit=256" in coordinator
    assert "tranche_size=256" in coordinator
    assert "receipt.sentence_count" in coordinator


def test_single_partition_workload_uses_same_worker_without_process_pool() -> None:
    source = STREAMING.read_text(encoding="utf-8")
    direct_start = source.index("if len(proposed_partitions) == 1:")
    pool_start = source.index("else:\n            context = mp.get_context", direct_start)
    direct = source[direct_start:pool_start]
    assert "_worker_drain(" in direct
    assert "ProcessPoolExecutor(" not in direct
    assert 'f"parser-direct:{run_ref}"' in direct
    assert "single-partition direct parser execution did not close coverage" in direct


def test_multi_partition_path_retains_spawned_pool() -> None:
    source = STREAMING.read_text(encoding="utf-8")
    assert 'context = mp.get_context("spawn")' in source
    assert "ProcessPoolExecutor(" in source
    assert "initializer=linux_parent_death_initializer" in source


def test_receipt_declares_parser_execution_mode() -> None:
    source = STREAMING.read_text(encoding="utf-8")
    assert '"parser_execution_mode": (' in source
    assert '"direct_single_partition"' in source
    assert '"spawned_process_pool"' in source
