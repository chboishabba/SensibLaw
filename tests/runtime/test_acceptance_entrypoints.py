from __future__ import annotations

import runpy
from pathlib import Path


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
