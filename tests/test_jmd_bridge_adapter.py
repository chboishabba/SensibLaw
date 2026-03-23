from __future__ import annotations

import json
from pathlib import Path

from src.ingestion.jmd_bridge import build_jmd_sl_bridge_artifacts


def test_build_jmd_sl_bridge_artifacts_from_runtime_example() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runtime_object = json.loads(
        (repo_root / "examples" / "jmd_bridge" / "jmd_runtime_object_minimal.json").read_text(encoding="utf-8")
    )
    payloads = build_jmd_sl_bridge_artifacts(runtime_object)
    ingest = payloads["ingest"]
    overlay = payloads["overlay"]

    obj = ingest["objects"][0]
    assert ingest["bridge_version"] == "jmd.sl.ingest.v1"
    assert obj["object_id"] == "jmd:erdfa:shard:note-0001"
    assert obj["text"] == "Alice paid Bob on 2026-03-19. Receipt hash: abc123."
    assert obj["content_ref"]["paste_ref"]["provider"] == "kant-zk-pastebin"

    anchor = overlay["anchors"][0]
    assert overlay["bridge_version"] == "sl.jmd.overlay.v1"
    assert anchor["source_object_id"] == "jmd:erdfa:shard:note-0001"
    assert anchor["anchored_text"] == obj["text"]
    assert anchor["byte_end"] == len(obj["text"].encode("utf-8"))
    assert overlay["overlays"][0]["detail"]["confidence"] == "advisory"
