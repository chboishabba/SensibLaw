from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_strict_iteration_probe.py"


def test_iteration_probe_is_explicitly_non_accepting() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"acceptance_eligible": False' in source
    assert '"partial_run_evidence": True' in source
    assert '"semantic_authority_effect": "none"' in source
    assert '"semantic_identity_effect": "none"' in source


def test_iteration_probe_observes_sql_outside_semantic_transaction() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "psycopg.connect(database_url, autocommit=True)" in source
    assert "pg_stat_activity" in source
    assert "pg_locks" in source
    assert "pg_stat_user_tables" in source
    assert "pg_stat_statements" in source


def test_iteration_probe_preserves_existing_owner_and_resource_receipts() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "run_strict_tranche_acceptance.py" in source
    assert "resource-checkpoints" in source
    assert "rss.jsonl" in source
    assert "acceptance-receipt.json" in source


def test_iteration_probe_has_a_bounded_operator_kill() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'parser.add_argument("--seconds"' in source
    assert "process.send_signal(signal.SIGTERM)" in source
    assert "process.wait(timeout=30)" in source
