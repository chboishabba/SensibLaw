from __future__ import annotations

import json
from pathlib import Path

from scripts import source_pack_manifest_pull as pull


def test_manifest_pull_indexes_seed_paths_without_network(tmp_path: Path) -> None:
    # Create a local fixture file to index.
    local = tmp_path / "doc.txt"
    local.write_text("hello world", encoding="utf-8")

    pack = {
        "pack_id": "seed_paths_test",
        "sources": [
            {
                "id": "local",
                "name": "Local files",
                "seed_urls": [],
                "seed_paths": [str(local)],
            }
        ],
    }
    pack_path = tmp_path / "pack.json"
    pack_path.write_text(json.dumps(pack), encoding="utf-8")

    out_dir = tmp_path / "out"
    res = pull.run(
        pack_path=pack_path,
        out_dir=out_dir,
        timeout=5,
        max_links_per_doc=5,
        max_authority_links_per_doc=5,
        legal_rps=1.0,
        wiki_rps=1.0,
        default_rps=1.0,
    )
    assert res["ok"] is True
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    docs = manifest.get("documents") or []
    assert len(docs) == 1
    assert docs[0]["status"] == "ok"
    assert docs[0]["seed_path"] == str(local)
    assert docs[0]["raw_path"] == str(local)  # no duplication for local binaries
