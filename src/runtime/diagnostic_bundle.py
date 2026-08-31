"""Small fail-safe diagnostic bundler for benchmark artifact directories."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tarfile
from typing import Any, Mapping


def write_json_receipt(
    artifact_root: str | Path,
    payload: Mapping[str, Any],
    *,
    filename: str,
) -> Path:
    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / filename
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def bundle_artifact_directory(artifact_root: str | Path) -> Path:
    """Atomically archive an artifact folder, then remove the unpacked copy."""

    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    archive = root.parent / f"{root.name}.tar.xz"
    temporary = archive.with_suffix(archive.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with tarfile.open(temporary, mode="w:xz") as handle:
        handle.add(root, arcname=root.name, recursive=True)
    temporary.replace(archive)
    shutil.rmtree(root)
    return archive


__all__ = ["bundle_artifact_directory", "write_json_receipt"]
