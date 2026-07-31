from __future__ import annotations

import runpy
from pathlib import Path

from src.runtime.active_document_resources import ActiveDocumentResourceGuard


def test_complete_tranche_entrypoint_imports_without_pnf_cycle(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(
        "sys.argv",
        [str(root / "scripts" / "run_complete_tranche.py"), "--help"],
    )
    try:
        runpy.run_path(
            str(root / "scripts" / "run_complete_tranche.py"),
            run_name="__main__",
        )
    except SystemExit as error:
        assert error.code == 0


def test_strict_acceptance_entrypoint_imports(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(
        "sys.argv",
        [str(root / "scripts" / "run_strict_tranche_acceptance.py"), "--help"],
    )
    try:
        runpy.run_path(
            str(root / "scripts" / "run_strict_tranche_acceptance.py"),
            run_name="__main__",
        )
    except SystemExit as error:
        assert error.code == 0


def test_strict_acceptance_derives_limits_from_observed_peak() -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(str(root / "scripts" / "run_strict_tranche_acceptance.py"))

    limits = namespace["_derived_limits"]({"rss_bytes": 600 * 1024 * 1024})

    assert limits["rss"]["observed_peak_bytes"] == 600 * 1024 * 1024
    assert limits["rss"]["soft_limit_bytes"] > limits["rss"]["observed_peak_bytes"]
    assert limits["rss"]["hard_limit_bytes"] > limits["rss"]["soft_limit_bytes"]


def test_resource_guard_retains_all_stage_checkpoints_only_when_requested(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_DIR", str(tmp_path))
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_ALL", "1")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB", "4096")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB", "4097")

    ActiveDocumentResourceGuard(document_ref="document:calibration").checkpoint(
        stage="parser_annotation",
        current_kernel="stage_boundary_after",
    )

    paths = list(tmp_path.glob("*.resource-checkpoint.json"))
    assert len(paths) == 1
    assert "parser_annotation.stage_boundary_after" in paths[0].name
