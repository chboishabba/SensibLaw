from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import runpy
from pathlib import Path
import subprocess
import sys

import pytest

from src.runtime.active_document_resources import ActiveDocumentResourceGuard
from src.runtime.semantic_worker_probe import probe_semantic_worker_imports


@pytest.mark.parametrize(
    "script_name",
    (
        "run_complete_tranche.py",
        "run_strict_tranche_acceptance.py",
        "run_exact_0008_calibration.py",
        "run_exact_0008_parallel_acceptance.py",
        "normalize_exact_0008_baseline.py",
    ),
)
def test_acceptance_entrypoint_imports_without_pnf_cycle(
    monkeypatch, script_name: str
) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / script_name
    monkeypatch.setattr("sys.argv", [str(script), "--help"])
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as error:
        assert error.code == 0


def test_public_interface_import_does_not_load_spacy_runtime() -> None:
    root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        "-c",
        (
            "import sys; "
            "import src.sensiblaw.interfaces; "
            "assert 'src.nlp.spacy_adapter' not in sys.modules; "
            "assert 'spacy' not in sys.modules"
        ),
    ]

    completed = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_semantic_worker_import_does_not_load_spacy_runtime() -> None:
    start_method = (
        "forkserver"
        if "forkserver" in multiprocessing.get_all_start_methods()
        else "spawn"
    )
    with ProcessPoolExecutor(
        max_workers=1,
        mp_context=multiprocessing.get_context(start_method),
    ) as executor:
        probe = executor.submit(probe_semantic_worker_imports).result(timeout=60)

    assert probe["policy_worker_module_loaded"] is True
    assert probe["spacy_loaded"] is False
    assert probe["spacy_adapter_loaded"] is False
    assert probe["parser_runtime_loaded"] is False


def test_strict_acceptance_derives_limits_from_observed_peak() -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "run_strict_tranche_acceptance.py")
    )

    limits = namespace["_derived_limits"]({"rss_bytes": 600 * 1024 * 1024})

    assert limits["rss"]["observed_peak_bytes"] == 600 * 1024 * 1024
    assert limits["rss"]["soft_limit_bytes"] > limits["rss"]["observed_peak_bytes"]
    assert limits["rss"]["hard_limit_bytes"] > limits["rss"]["soft_limit_bytes"]


def test_exact_acceptance_requires_observed_semantic_processes() -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "run_exact_0008_parallel_acceptance.py")
    )

    observed = namespace["_process_parallelism"](
        {
            "typing_hierarchies": {
                "matching": {"worker_pids": [101, 102]},
                "typing": {"worker_pids": [102, 103]},
            },
            "closure_audit": {
                "process_worker_pid:104": 3,
                "process_worker_pid:105": 0,
                "activation": {"worker_pids": [106, 107]},
            },
        }
    )
    serial = namespace["_process_parallelism"](
        {
            "typing_hierarchies": {"matching": {"worker_pids": [101]}},
            "closure_audit": {},
        }
    )

    assert observed["distinct_semantic_worker_pids"] == [101, 102, 103, 104, 106, 107]
    assert observed["closure_activation_worker_pids"] == [106, 107]
    assert observed["parallel_process_execution_observed"] is True
    assert serial["parallel_process_execution_observed"] is False


def test_parallel_acceptance_is_explicitly_rolled_back() -> None:
    root = Path(__file__).resolve().parents[2]
    # The executable command is assembled in main; assert the source contract
    # directly so a future runner edit cannot silently publish calibration rows.
    source = (root / "scripts" / "run_exact_0008_parallel_acceptance.py").read_text()
    assert '"--calibration"' in source


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
