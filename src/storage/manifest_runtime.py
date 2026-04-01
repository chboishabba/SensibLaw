from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .repo_roots import resolve_sensiblaw_relative


def resolve_sensiblaw_manifest_path(*segments: str | Path) -> Path:
    return resolve_sensiblaw_relative(*segments)


def load_json_object(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"expected JSON object at {resolved}")
    return dict(payload)


def load_versioned_json_object(path: str | Path, *, expected_version: str) -> dict[str, Any]:
    payload = load_json_object(path)
    if payload.get("version") != expected_version:
        raise ValueError(f"unsupported manifest version: {payload.get('version')}")
    return payload


__all__ = [
    "load_json_object",
    "load_versioned_json_object",
    "resolve_sensiblaw_manifest_path",
]
