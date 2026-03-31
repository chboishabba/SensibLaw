from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def relative_repo_path(path: Path, *, repo_root: Path) -> str:
    return str(path.resolve().relative_to(repo_root))


def write_json_markdown_artifact(
    *,
    output_dir: Path,
    artifact_version: str,
    payload: dict[str, Any],
    summary_text: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{artifact_version}.json"
    summary_path = output_dir / f"{artifact_version}.summary.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(summary_text, encoding="utf-8")
    return {
        "artifact_path": str(artifact_path),
        "summary_path": str(summary_path),
    }


__all__ = [
    "load_json_object",
    "relative_repo_path",
    "write_json_markdown_artifact",
]
