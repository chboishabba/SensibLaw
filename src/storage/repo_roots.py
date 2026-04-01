from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def sensiblaw_root() -> Path:
    return repo_root() / "SensibLaw"


def resolve_sensiblaw_root(script_file: str | Path) -> Path:
    script_path = Path(script_file).expanduser().resolve()
    root = script_path.parents[1]
    if root.name != "SensibLaw":
        raise ValueError(f"expected script under SensibLaw/, got: {script_path}")
    return root


def resolve_repo_root(script_file: str | Path) -> Path:
    return resolve_sensiblaw_root(script_file).parent


def resolve_repo_relative(*segments: str | Path) -> Path:
    return repo_root().joinpath(*segments)


def resolve_sensiblaw_relative(*segments: str | Path) -> Path:
    return sensiblaw_root().joinpath(*segments)


def relative_repo_path(path: Path | str, *, base: Path | None = None) -> str:
    root = base or repo_root()
    resolved_path = Path(path).expanduser().resolve()
    resolved_root = Path(root).expanduser().resolve()
    try:
        return str(resolved_path.relative_to(resolved_root))
    except ValueError:
        return str(resolved_path)


__all__ = [
    "relative_repo_path",
    "repo_root",
    "resolve_repo_root",
    "resolve_repo_relative",
    "resolve_sensiblaw_root",
    "resolve_sensiblaw_relative",
    "sensiblaw_root",
]
