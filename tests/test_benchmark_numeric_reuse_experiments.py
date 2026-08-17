from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_numeric_reuse_experiments.py"
FIXTURE_MANIFEST = ROOT / "data" / "benchmarks" / "numeric_reuse_v1" / "manifest.json"


@pytest.fixture(scope="module")
def benchmark_module():
    spec = importlib.util.spec_from_file_location("numeric_reuse_benchmark", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _copied_manifest(tmp_path: Path) -> Path:
    destination = tmp_path / "numeric_reuse_v1"
    shutil.copytree(FIXTURE_MANIFEST.parent, destination)
    return destination / "manifest.json"


def test_pinned_fixture_loads_and_resolves_all_inputs(benchmark_module) -> None:
    fixture = benchmark_module.load_fixture_manifest(FIXTURE_MANIFEST)

    assert fixture["fixture_id"] == "numeric_reuse_v1"
    assert set(fixture["resolved_inputs"]) == {"cold", "edit", "domain"}
    assert all(path.is_file() for path in fixture["resolved_inputs"].values())


def test_fixture_rejects_digest_drift(benchmark_module, tmp_path: Path) -> None:
    manifest = _copied_manifest(tmp_path)
    cold = manifest.parent / "native_title_cold_12k.txt"
    cold.write_text(cold.read_text(encoding="utf-8") + "\nDrift.", encoding="utf-8")

    with pytest.raises(ValueError, match="digest drift"):
        benchmark_module.load_fixture_manifest(manifest)


def test_manifest_validation_happens_before_database_access(
    benchmark_module, monkeypatch, tmp_path: Path
) -> None:
    manifest = _copied_manifest(tmp_path)
    cold = manifest.parent / "native_title_cold_12k.txt"
    cold.write_text(cold.read_text(encoding="utf-8") + "\nDrift.", encoding="utf-8")
    database_accessed = False

    def fail_if_called(database_url: str) -> None:
        nonlocal database_accessed
        database_accessed = True

    monkeypatch.setattr(benchmark_module, "_assert_empty", fail_if_called)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark",
            "--database-url",
            "postgresql://example",
            "--fixture-manifest",
            str(manifest),
            "--output-root",
            str(tmp_path / "output"),
            "--require-empty-receipt-table",
        ],
    )

    with pytest.raises(ValueError, match="digest drift"):
        benchmark_module.main()
    assert not database_accessed


@pytest.mark.parametrize("duplicate", [("edit", "cold"), ("domain", "cold")])
def test_fixture_rejects_duplicate_semantic_inputs(
    benchmark_module, tmp_path: Path, duplicate: tuple[str, str]
) -> None:
    manifest_path = _copied_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target, source = duplicate
    manifest["inputs"][target]["path"] = manifest["inputs"][source]["path"]
    manifest["inputs"][target]["sha256"] = manifest["inputs"][source]["sha256"]
    manifest["inputs"][target]["bytes"] = manifest["inputs"][source]["bytes"]
    manifest["inputs"][target]["token_count"] = manifest["inputs"][source][
        "token_count"
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="must differ"):
        benchmark_module.load_fixture_manifest(manifest_path)


def test_explicit_input_arguments_remain_supported(
    benchmark_module, monkeypatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark",
            "--database-url",
            "postgresql://example",
            "--cold-input",
            "cold.txt",
            "--edit-input",
            "edit.txt",
            "--domain-input",
            "domain.txt",
            "--output-root",
            "out",
        ],
    )

    args = benchmark_module._parse_args()

    assert args.fixture_manifest is None
    assert args.cold_input == Path("cold.txt")
    assert args.edit_input == Path("edit.txt")
    assert args.domain_input == Path("domain.txt")


def test_explicit_input_workflow_does_not_require_a_fixture(
    benchmark_module, monkeypatch, tmp_path: Path
) -> None:
    paths = {name: tmp_path / f"{name}.txt" for name in ("cold", "edit", "domain")}
    for name, path in paths.items():
        path.write_text(f"{name} source", encoding="utf-8")
    calls: list[tuple[str, Path]] = []

    def fake_run(label, input_path, root, args, reference=None, leaf_audit=False):
        calls.append((label, input_path))
        receipt = {"receipt_sha256": label, "receipt_compute_ns": 0}
        return {
            "accepted": True,
            "receipt": receipt,
            "receipt_path": str(root / label / "receipt.json"),
            "receipt_source": "durable_build",
            "receipt_compute_seconds": 0.0,
            "numeric_semantic_parity": {"semantic_parity": label == "exact-replay"},
            "numeric_work_timing": {"post_parser_work_ns_per_token": 1.0},
        }

    monkeypatch.setattr(benchmark_module, "_run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark",
            "--database-url",
            "postgresql://example",
            "--cold-input",
            str(paths["cold"]),
            "--edit-input",
            str(paths["edit"]),
            "--domain-input",
            str(paths["domain"]),
            "--output-root",
            str(tmp_path / "output"),
        ],
    )

    assert benchmark_module.main() == 0
    assert calls == [
        ("cold", paths["cold"].resolve()),
        ("exact-replay", paths["cold"].resolve()),
        ("small-edit", paths["edit"].resolve()),
        ("same-domain-new-document", paths["domain"].resolve()),
    ]


def test_manifest_and_explicit_inputs_are_exclusive(
    benchmark_module, monkeypatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark",
            "--database-url",
            "postgresql://example",
            "--fixture-manifest",
            "manifest.json",
            "--cold-input",
            "cold.txt",
            "--output-root",
            "out",
        ],
    )

    with pytest.raises(SystemExit):
        benchmark_module._parse_args()


def test_leaf_locality_requirement_is_opt_in(benchmark_module, monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark",
            "--database-url",
            "postgresql://example",
            "--cold-input",
            "cold.txt",
            "--edit-input",
            "edit.txt",
            "--domain-input",
            "domain.txt",
            "--output-root",
            "out",
            "--require-small-edit-leaf-locality",
        ],
    )

    assert benchmark_module._parse_args().require_small_edit_leaf_locality
