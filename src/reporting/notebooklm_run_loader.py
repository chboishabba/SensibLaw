from __future__ import annotations

from pathlib import Path
from typing import Callable


def is_date_text(value: str) -> bool:
    return len(value) == 10 and value[4] == "-" and value[7] == "-" and value.replace("-", "").isdigit()


def resolve_runs_root(runs_root: str | Path) -> Path:
    return Path(runs_root).expanduser().resolve()


def iter_dated_artifacts(
    runs_root: str | Path,
    *,
    relative_path: tuple[str, ...] | Callable[[str], tuple[str, ...]],
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[tuple[str, Path]]:
    root = resolve_runs_root(runs_root)
    out: list[tuple[str, Path]] = []
    for entry in sorted(root.iterdir() if root.exists() else []):
        if not entry.is_dir() or not is_date_text(entry.name):
            continue
        date_text = entry.name
        if start_date and date_text < start_date:
            continue
        if end_date and date_text > end_date:
            continue
        path_parts = relative_path(date_text) if callable(relative_path) else relative_path
        target = entry.joinpath(*path_parts)
        if target.exists():
            out.append((date_text, target))
    return out
