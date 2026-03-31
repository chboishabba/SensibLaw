from __future__ import annotations

from pathlib import Path

from src.reporting.source_loaders import (
    find_timestamped_artifact_path,
    list_message_export_json_paths,
    resolve_loader_path,
)


def test_resolve_loader_path_returns_resolved_path(tmp_path: Path) -> None:
    path = tmp_path / "child" / "demo.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("demo", encoding="utf-8")

    assert resolve_loader_path(path) == path.resolve()


def test_list_message_export_json_paths_discovers_nested_message_files(tmp_path: Path) -> None:
    root = tmp_path / "export"
    nested = root / "inbox" / "thread-a"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "message_2.json").write_text("{}", encoding="utf-8")
    (nested / "message_1.json").write_text("{}", encoding="utf-8")

    paths = list_message_export_json_paths(root)

    assert [path.name for path in paths] == ["message_1.json", "message_2.json"]


def test_find_timestamped_artifact_path_prefers_exact_match(tmp_path: Path) -> None:
    screenshot_root = tmp_path / "screenshots"
    screenshot_root.mkdir(parents=True, exist_ok=True)
    exact = screenshot_root / "123.webp"
    indexed = screenshot_root / "123_1.webp"
    exact.write_bytes(b"exact")
    indexed.write_bytes(b"indexed")

    assert find_timestamped_artifact_path(search_roots=[screenshot_root], timestamp=123) == exact


def test_find_timestamped_artifact_path_falls_back_to_indexed_match(tmp_path: Path) -> None:
    screenshot_root = tmp_path / "screenshots"
    screenshot_root.mkdir(parents=True, exist_ok=True)
    indexed = screenshot_root / "123_2.webp"
    indexed.write_bytes(b"indexed")

    assert find_timestamped_artifact_path(search_roots=[screenshot_root], timestamp=123) == indexed
