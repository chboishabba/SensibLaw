from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "profile_sentence_close_function_kernels.py"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_profiler_uses_postgres_function_accounting_without_disabling_semantics() -> None:
    source = _source()
    assert "track_functions = 'pl'" in source
    assert "pg_stat_reset()" in source
    assert "pg_stat_user_functions" in source
    assert "DISABLE TRIGGER" not in source
    assert "session_replication_role" not in source
    assert '"semantic_authority_changed_by_profiler": False' in source
    assert '"triggers_disabled": False' in source
    assert '"functions_replaced": False' in source


def test_profiler_ranks_measured_function_wall() -> None:
    source = _source()
    assert "ORDER BY total_time DESC, self_time DESC" in source
    assert '"total_ms"' in source
    assert '"self_ms"' in source
    assert '"self_share"' in source
    assert '"top_functions"' in source


def test_profiler_executes_canonical_benchmark_as_separate_process() -> None:
    source = _source()
    assert "subprocess.run(" in source
    assert 'environment["DATABASE_URL"] = database_url' in source
    assert "shlex.split(command)" in source
    assert "return returncode" in source
