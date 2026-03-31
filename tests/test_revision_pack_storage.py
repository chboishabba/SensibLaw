from __future__ import annotations

import json
from pathlib import Path

from src.wiki_timeline.revision_pack_storage import (
    default_out_dir_for_pack,
    graph_artifact_path,
    pair_artifact_paths,
    read_json_file,
    revision_artifact_paths,
    slug_artifact_name,
    stable_json,
    write_json_file,
)


def test_revision_pack_storage_shapes_paths_and_json(tmp_path: Path) -> None:
    payload = {"b": 1, "a": {"z": 2}}
    out_path = tmp_path / "nested" / "artifact.json"
    write_json_file(out_path, payload)

    assert out_path.exists()
    assert read_json_file(out_path) == payload
    assert stable_json(payload) == '{"a":{"z":2},"b":1}'
    assert slug_artifact_name(" Example / Pack ") == "Example_Pack"

    current_paths = revision_artifact_paths(out_dir=tmp_path, article_id="article/one", revid=12)
    assert current_paths["snapshot"] == tmp_path / "snapshots" / "article_one__revid_12.json"
    assert current_paths["timeline"] == tmp_path / "timeline" / "article_one__revid_12.json"
    assert current_paths["aoo"] == tmp_path / "aoo" / "article_one__revid_12.json"

    pair_paths = pair_artifact_paths(
        out_dir=tmp_path,
        article_id="article/one",
        pair_kind="largest delta",
        older_revid=11,
        newer_revid=12,
    )
    assert pair_paths["pair_report"] == tmp_path / "pair_reports" / "article_one__largest_delta__11__12.json"
    assert pair_paths["older_snapshot"] == tmp_path / "pair_snapshots" / "article_one__largest_delta__11__12__older.json"
    assert graph_artifact_path(out_dir=tmp_path, article_id="article/one", run_id="run:1") == (
        tmp_path / "contested_graphs" / "article_one__run_1.json"
    )


def test_default_out_dir_for_pack_uses_storage_slugging(tmp_path: Path) -> None:
    pack_path = tmp_path / "pack.json"
    pack_path.write_text(json.dumps({"pack_id": "Pack / 42"}), encoding="utf-8")
    assert default_out_dir_for_pack(pack_path) == Path("SensibLaw/demo/ingest/wiki_revision_monitor/Pack_42")


def test_revision_pack_runner_imports_storage_owner() -> None:
    runner_path = Path(__file__).resolve().parents[1] / "src" / "wiki_timeline" / "revision_pack_runner.py"
    source = runner_path.read_text(encoding="utf-8")
    assert "from src.wiki_timeline.revision_pack_storage import (" in source
    assert "pair_artifact_paths(" in source
    assert "revision_artifact_paths(" in source
    assert "write_json_file(" in source
