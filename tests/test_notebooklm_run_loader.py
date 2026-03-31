from __future__ import annotations

from pathlib import Path

from src.reporting.notebooklm_run_loader import iter_dated_artifacts, resolve_runs_root


def test_notebooklm_run_loader_resolves_root_and_filters_dated_artifacts(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    good_a = runs_root / "2026-03-10" / "logs" / "notes"
    good_b = runs_root / "2026-03-11" / "outputs" / "notebooklm"
    bad = runs_root / "latest" / "logs" / "notes"
    good_a.mkdir(parents=True)
    good_b.mkdir(parents=True)
    bad.mkdir(parents=True)
    (good_a / "2026-03-10.jsonl").write_text("", encoding="utf-8")
    (good_b / "notebooklm_activity_normalized.jsonl").write_text("", encoding="utf-8")
    (bad / "latest.jsonl").write_text("", encoding="utf-8")

    assert resolve_runs_root(runs_root) == runs_root.resolve()
    notes = iter_dated_artifacts(
        runs_root,
        relative_path=lambda date_text: ("logs", "notes", f"{date_text}.jsonl"),
        start_date="2026-03-10",
        end_date="2026-03-10",
    )
    assert notes == [("2026-03-10", good_a / "2026-03-10.jsonl")]

    activity = iter_dated_artifacts(
        runs_root,
        relative_path=("outputs", "notebooklm", "notebooklm_activity_normalized.jsonl"),
    )
    assert activity == [("2026-03-11", good_b / "notebooklm_activity_normalized.jsonl")]


def test_notebooklm_modules_import_shared_run_loader() -> None:
    reporting_root = Path(__file__).resolve().parents[1] / "src" / "reporting"
    observer = (reporting_root / "notebooklm_observer.py").read_text(encoding="utf-8")
    activity = (reporting_root / "notebooklm_activity.py").read_text(encoding="utf-8")
    assert "from src.reporting.notebooklm_run_loader import iter_dated_artifacts, resolve_runs_root" in observer
    assert "from src.reporting.notebooklm_run_loader import iter_dated_artifacts" in activity
