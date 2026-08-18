from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ROOT / "scripts/run_complete_tranche_production.py"
TIMING = ROOT / "scripts/benchmark_complete_tranche_phases.py"
CALIBRATION = ROOT / "scripts/run_exact_0008_calibration.py"
HISTORICAL = ROOT / "scripts/run_complete_tranche.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_entrypoint_injects_strict_numeric_mode() -> None:
    module = _load(PRODUCTION, "_test_complete_tranche_production")

    assert module.production_argv(["--tranche", "GWB"]) == [
        "--strict-exact",
        "--tranche",
        "GWB",
    ]
    assert module.production_argv(["--strict-exact", "--tranche", "GWB"]) == [
        "--strict-exact",
        "--tranche",
        "GWB",
    ]


def test_timing_entrypoint_defaults_to_strict_numeric_and_compat_is_explicit() -> None:
    module = _load(TIMING, "_test_complete_tranche_timing")

    assert module._runner_strategy_args(
        compatibility_replay=False,
        passthrough=["--database-url", "postgresql://example/sensiblaw"],
    )[:1] == ["--strict-exact"]
    assert module._runner_strategy_args(
        compatibility_replay=True,
        passthrough=["--database-url", "postgresql://example/sensiblaw"],
    ) == ["--database-url", "postgresql://example/sensiblaw"]


def test_timing_rejects_conflicting_compatibility_and_strict_requests() -> None:
    module = _load(TIMING, "_test_complete_tranche_timing_conflict")

    with pytest.raises(ValueError):
        module._runner_strategy_args(
            compatibility_replay=True,
            passthrough=["--strict-exact"],
        )


def test_exact_0008_calibration_defaults_to_strict_numeric() -> None:
    module = _load(CALIBRATION, "_test_exact_0008_calibration_default")

    assert module._runner_strategy_args(compatibility_replay=False) == [
        "--strict-exact"
    ]
    assert module._runner_strategy_args(compatibility_replay=True) == []
    with pytest.raises(ValueError):
        module._runner_strategy_args(
            compatibility_replay=True,
            strict_exact=True,
        )


def test_historical_runner_compatibility_default_is_documented_as_nonproduction() -> (
    None
):
    historical = HISTORICAL.read_text(encoding="utf-8")
    production = PRODUCTION.read_text(encoding="utf-8")

    assert 'else "local-compatibility-replay"' in historical
    assert "historical" in production.lower()
    assert "production" in production.lower()
    assert '"--strict-exact"' in production
