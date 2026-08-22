from __future__ import annotations

from argparse import Namespace
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
import runpy
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

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


def test_pg_stat_statements_provisioning_requires_extension_and_preload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "run_strict_tranche_acceptance.py")
    )

    class Cursor:
        def __enter__(self) -> "Cursor":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, *_args: object, **_kwargs: object) -> None:
            return None

        def fetchone(self) -> tuple[bool, str]:
            return True, "pg_stat_statements"

    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def cursor(self) -> Cursor:
            return Cursor()

    monkeypatch.setitem(
        sys.modules, "psycopg", SimpleNamespace(connect=lambda _url: Connection())
    )

    assert namespace["_enable_pg_stat_statements"]("postgresql://test") == {
        "state": "enabled",
        "extension": "pg_stat_statements",
        "shared_preload_libraries": ["pg_stat_statements"],
    }


def test_strict_acceptance_accepts_reused_published_compilation(
    monkeypatch, tmp_path: Path
) -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "run_strict_tranche_acceptance.py")
    )
    source = tmp_path / "source.txt"
    source.write_text("bounded source", encoding="utf-8")
    output = tmp_path / "output"
    tranche_root = output / "gwb"
    projection_root = tranche_root / "source_projection"
    projection_root.mkdir(parents=True)
    raw_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    document_ref = "document:test"
    (projection_root / "manifest.json").write_text(
        json.dumps({"documents": [{"raw_sha256": raw_sha256}]}),
        encoding="utf-8",
    )
    (tranche_root / "local_pnf_compilation.json").write_text(
        json.dumps({"corpus_ref": "corpus:test", "document_refs": [document_ref]}),
        encoding="utf-8",
    )

    class Cursor:
        def __init__(self) -> None:
            self._rows = iter(
                (
                    [(document_ref, "reused_compilation")],
                    [(document_ref, 1)],
                    [(document_ref, 1, True)],
                    [(document_ref, 1)],
                )
            )

        def __enter__(self) -> "Cursor":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, *_args: object, **_kwargs: object) -> None:
            return None

        def fetchall(self) -> list[tuple[object, ...]]:
            return next(self._rows)

    class Connection:
        def __init__(self) -> None:
            self._cursor = Cursor()

        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def cursor(self) -> Cursor:
            return self._cursor

    monkeypatch.setitem(
        sys.modules,
        "psycopg",
        SimpleNamespace(connect=lambda _database_url: Connection()),
    )
    result = namespace["_verify_explicit_publication"](
        Namespace(
            input_path=(source,),
            output_root=output,
            tranche="GWB",
            database_url="postgresql://test",
        )
    )

    assert result["state"] == "verified"


def test_strict_acceptance_accepts_closed_numeric_pnf_publication(
    monkeypatch, tmp_path: Path
) -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "run_strict_tranche_acceptance.py")
    )
    source = tmp_path / "source.txt"
    source.write_text("bounded source", encoding="utf-8")
    output = tmp_path / "output"
    tranche_root = output / "gwb"
    projection_root = tranche_root / "source_projection"
    projection_root.mkdir(parents=True)
    raw_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    document_ref = "document:test"
    (projection_root / "manifest.json").write_text(
        json.dumps({"documents": [{"raw_sha256": raw_sha256}]}),
        encoding="utf-8",
    )
    (tranche_root / "local_pnf_compilation.json").write_text(
        json.dumps({"corpus_ref": "corpus:test", "document_refs": [document_ref]}),
        encoding="utf-8",
    )

    class Cursor:
        def __init__(self) -> None:
            self._rows = iter(
                (
                    [(document_ref, "compiled_numeric_pnf")],
                    [(document_ref, 1)],
                    [],
                    [],
                    [(document_ref, 1)],
                )
            )

        def __enter__(self) -> "Cursor":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, *_args: object, **_kwargs: object) -> None:
            return None

        def fetchall(self) -> list[tuple[object, ...]]:
            return next(self._rows)

    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def cursor(self) -> Cursor:
            return Cursor()

    monkeypatch.setitem(
        sys.modules,
        "psycopg",
        SimpleNamespace(connect=lambda _database_url: Connection()),
    )
    result = namespace["_verify_explicit_publication"](
        Namespace(
            input_path=(source,),
            output_root=output,
            tranche="GWB",
            database_url="postgresql://test",
        )
    )

    assert result["state"] == "verified"
    assert result["publication_authority"] == "numeric_pnf"


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


def test_strict_acceptance_stops_an_over_limit_process_group(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "run_strict_tranche_acceptance.py")
    )
    signals: list[tuple[int, int]] = []

    class Process:
        pid = 123

        @staticmethod
        def poll():
            return None

        @staticmethod
        def terminate():
            raise AssertionError("process-group termination should be preferred")

    monkeypatch.setattr(
        namespace["os"], "killpg", lambda pid, sig: signals.append((pid, sig))
    )

    assert namespace["_terminate_process_group"](Process()) == "process_group_sigterm"
    assert signals == [(123, namespace["signal"].SIGTERM)]


def test_strict_acceptance_summarizes_resource_checkpoints(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "run_strict_tranche_acceptance.py")
    )
    (tmp_path / "first.resource-checkpoint.json").write_text(
        '{"active_stage":"graph","current_kernel":"after",'
        '"resources":{"rss_bytes":100,"process_tree_rss_bytes":200}}',
        encoding="utf-8",
    )
    (tmp_path / "second.resource-checkpoint.json").write_text(
        '{"active_stage":"graph","current_kernel":"after",'
        '"resources":{"rss_bytes":150,"process_tree_rss_bytes":175}}',
        encoding="utf-8",
    )

    assert namespace["_checkpoint_stage_peaks"](tmp_path) == {
        "graph:after": {"rss_bytes": 150, "process_tree_rss_bytes": 200}
    }


def test_strict_acceptance_loads_only_one_direct_progress_timing(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "run_strict_tranche_acceptance.py")
    )
    progress_path = tmp_path / "gwb" / "local_pnf_compile_progress.json"
    progress_path.parent.mkdir(parents=True)
    progress_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "details": {
                            "numeric_work_timing": {
                                "spacy_parser_wall_occupancy_ns": 1000,
                                "post_parser_wall_occupancy_ns": 100,
                                "timing_basis": "monotonic-wall-occupancy:v3",
                            }
                        }
                    }
                ],
                "outer_phase_seconds": {"LOCAL_PNF_COMPILATION": 6358.0},
            }
        ),
        encoding="utf-8",
    )

    result = namespace["_numeric_timing_from_progress"](
        Namespace(output_root=tmp_path, tranche="GWB")
    )

    assert result["state"] == "measured"
    assert result["timing_record_count"] == 1
    assert result["numeric_work_timing"]["post_parser_wall_occupancy_ns"] == 100


def test_strict_acceptance_rejects_multiple_progress_timing_records(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "run_strict_tranche_acceptance.py")
    )
    progress_path = tmp_path / "gwb" / "local_pnf_compile_progress.json"
    progress_path.parent.mkdir(parents=True)
    progress_path.write_text(
        json.dumps({"events": [{"details": {"numeric_work_timing": {}}}] * 2}),
        encoding="utf-8",
    )

    result = namespace["_numeric_timing_from_progress"](
        Namespace(output_root=tmp_path, tranche="GWB")
    )

    assert result["state"] == "unknown"
    assert result["timing_record_count"] == 2


@pytest.mark.parametrize(
    ("post_parser_ns", "expected_gate", "expected_reason"),
    (
        (100, "pass", None),
        (101, "fail", "parser_relative_performance_target_exceeded"),
    ),
)
def test_strict_acceptance_enforces_parser_relative_gate(
    post_parser_ns: int,
    expected_gate: str,
    expected_reason: str | None,
) -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "run_strict_tranche_acceptance.py")
    )

    outcome = namespace["_strict_performance_outcome"](
        semantic_accepted=True,
        timing_evidence={
            "numeric_work_timing": {
                "spacy_parser_wall_occupancy_ns": 1000,
                "post_parser_wall_occupancy_ns": post_parser_ns,
                "timing_basis": "monotonic-wall-occupancy:v3",
            }
        },
    )

    assert outcome["performance_gate"] == expected_gate
    assert outcome["accepted"] is (expected_gate == "pass")
    assert outcome["failure_reason"] == expected_reason


def test_strict_acceptance_fails_closed_without_direct_timing() -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "run_strict_tranche_acceptance.py")
    )

    outcome = namespace["_strict_performance_outcome"](
        semantic_accepted=True,
        timing_evidence={"state": "unknown"},
    )

    assert outcome["performance_gate"] == "unknown"
    assert outcome["accepted"] is False
    assert outcome["failure_reason"] == "parser_relative_performance_unmeasured"


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
