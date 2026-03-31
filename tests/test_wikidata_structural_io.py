from __future__ import annotations

import json
from pathlib import Path

from src.policy.wikidata_structural_io import (
    load_json_object,
    relative_repo_path,
    write_json_markdown_artifact,
)


def test_load_json_object_reads_dict_payload(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    path.write_text(json.dumps({"a": 1}), encoding="utf-8")

    assert load_json_object(path) == {"a": 1}


def test_relative_repo_path_returns_repo_relative_string(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    target = repo_root / "nested" / "payload.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")

    assert relative_repo_path(target, repo_root=repo_root) == "nested/payload.json"


def test_write_json_markdown_artifact_emits_both_files(tmp_path: Path) -> None:
    paths = write_json_markdown_artifact(
        output_dir=tmp_path,
        artifact_version="demo_v1",
        payload={"version": "demo_v1"},
        summary_text="# Demo\n",
    )

    assert Path(paths["artifact_path"]).exists()
    assert Path(paths["summary_path"]).exists()
