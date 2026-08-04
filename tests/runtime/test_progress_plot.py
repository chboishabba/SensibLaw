from __future__ import annotations

from pathlib import Path

from src.runtime.progress_plot import metric_points, render_progress_plots, stage_intervals


def _ledger() -> dict:
    return {
        "schema_version": "sl.phase_ledger.v0_1",
        "events": [
            {
                "phase": "postgres_demand_planning_document_compile",
                "state": "stage_started",
                "subject_ref": "0007.txt",
                "message": "parser_observation_projection",
                "active_stage": "parser_observation_projection",
                "elapsed_ms": 1_000,
                "observed_at": "2026-07-28T00:00:01+00:00",
                "measures": {
                    "sentences_projected": {
                        "completed": 100,
                        "unit": "sentences",
                        "per_second": 100.0,
                    }
                },
            },
            {
                "phase": "postgres_demand_planning_document_compile",
                "state": "running",
                "subject_ref": "0007.txt",
                "message": "parser_observation_projection",
                "active_stage": "parser_observation_projection",
                "elapsed_ms": 2_000,
                "observed_at": "2026-07-28T00:00:02+00:00",
                "measures": {
                    "sentences_projected": {
                        "completed": 250,
                        "unit": "sentences",
                        "per_second": 125.0,
                    },
                    "parser_tokens_projected": {
                        "completed": 3_000,
                        "unit": "tokens",
                        "per_second": 1_500.0,
                    },
                },
            },
            {
                "phase": "postgres_demand_planning_document_compile",
                "state": "stage_completed",
                "subject_ref": "0007.txt",
                "message": "parser_observation_projection",
                "elapsed_ms": 4_000,
                "observed_at": "2026-07-28T00:00:04+00:00",
            },
        ],
    }


def test_extracts_metric_points_and_stage_intervals() -> None:
    ledger = _ledger()
    points = metric_points(ledger["events"])
    intervals = stage_intervals(ledger["events"])

    assert {point.metric for point in points} == {
        "sentences_projected",
        "parser_tokens_projected",
    }
    assert len(intervals) == 1
    assert intervals[0].subject_ref == "0007.txt"
    assert intervals[0].stage == "parser_observation_projection"
    assert intervals[0].started_seconds == 1.0
    assert intervals[0].ended_seconds == 4.0


def test_renders_directly_from_existing_ledger(tmp_path: Path) -> None:
    manifest = render_progress_plots(_ledger(), tmp_path, formats=("png",))

    assert manifest["source_event_count"] == 3
    assert manifest["metric_point_count"] == 3
    assert manifest["stage_interval_count"] == 1
    assert manifest["authority"] == "diagnostic_projection_only"
    assert Path(manifest["manifest_path"]).is_file()
    assert any(Path(path).name == "stage_timeline.png" for path in manifest["outputs"])
    assert all(Path(path).is_file() for path in manifest["outputs"])
