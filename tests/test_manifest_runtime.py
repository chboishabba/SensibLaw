from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.storage.manifest_runtime import (
    load_json_object,
    load_versioned_json_object,
    resolve_sensiblaw_manifest_path,
)


def test_resolve_sensiblaw_manifest_path_targets_repo_owned_location() -> None:
    path = resolve_sensiblaw_manifest_path("data", "fact_review", "wave1_legal_fixture_manifest_v1.json")
    assert path.name == "wave1_legal_fixture_manifest_v1.json"
    assert path.exists()


def test_load_json_object_requires_top_level_mapping(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="expected JSON object"):
        load_json_object(path)


def test_load_versioned_json_object_checks_expected_version(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"version": "v1"}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported manifest version"):
        load_versioned_json_object(path, expected_version="v2")
