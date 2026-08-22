from src.storage.postgres.region_close_trigger_probe import plan_metrics


def test_plan_metrics_preserves_unknown_unsupported_fields() -> None:
    metrics = plan_metrics(
        [
            {
                "Planning Time": 1.2,
                "Execution Time": 3.4,
                "Triggers": [{"Trigger Name": "close"}],
                "Plan": {"Shared Hit Blocks": 9, "WAL Records": 4},
            }
        ]
    )

    assert metrics["execution_time_ms"] == 3.4
    assert metrics["trigger_metrics"] == [{"Trigger Name": "close"}]
    assert metrics["shared_hit_blocks"] == 9
    assert metrics["wal_records"] == 4
    assert metrics["temp_read_blocks"] == "unknown"
