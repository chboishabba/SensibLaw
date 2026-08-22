from src.runtime.postgres_provisioning import _database_name


def test_retained_database_names_do_not_reuse_a_truncated_run_prefix() -> None:
    run_ref = "gwb-prefix-close-512-m175-token-explain-retry"

    first = _database_name(run_ref)
    second = _database_name(run_ref)

    assert first.startswith("sensiblaw_strict_")
    assert second.startswith("sensiblaw_strict_")
    assert first != second
    assert len(first) <= 63
    assert len(second) <= 63
