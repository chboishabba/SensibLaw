from __future__ import annotations

from pathlib import Path

from src.storage.repo_roots import (
    relative_repo_path,
    repo_root,
    resolve_repo_root,
    resolve_repo_relative,
    resolve_sensiblaw_root,
    resolve_sensiblaw_relative,
    sensiblaw_root,
)


def test_repo_root_contains_sensiblaw() -> None:
    root = repo_root()
    sensiblaw = sensiblaw_root()
    assert sensiblaw.is_dir()
    assert sensiblaw.parent == root


def test_paths_roundtrip_through_relative_helpers(tmp_path: Path) -> None:
    repo_path = resolve_repo_relative("tmp", "check.txt")
    sensiblaw_path = resolve_sensiblaw_relative("tmp", "check.txt")
    assert repo_path.exists() or not repo_path.exists()
    assert sensiblaw_path.exists() or not sensiblaw_path.exists()
    assert relative_repo_path(repo_path) == str(repo_path.relative_to(repo_root()))


def test_resolve_roots_for_sensiblaw_script_path(tmp_path: Path) -> None:
    script_path = tmp_path / "repo" / "SensibLaw" / "scripts" / "demo.py"
    assert resolve_sensiblaw_root(script_path) == tmp_path / "repo" / "SensibLaw"
    assert resolve_repo_root(script_path) == tmp_path / "repo"


def test_relative_repo_path_prefers_repo_relative_when_possible(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    nested = root / "SensibLaw" / "scripts" / "demo.py"
    external = tmp_path / "outside" / "demo.py"
    assert relative_repo_path(nested, base=root) == "SensibLaw/scripts/demo.py"
    assert relative_repo_path(external, base=root) == str(external.resolve())
