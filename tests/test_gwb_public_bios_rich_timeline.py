from __future__ import annotations

import json
from pathlib import Path

from scripts.build_gwb_public_bios_rich_timeline import build_public_bios_timeline

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_build_gwb_public_bios_rich_timeline(tmp_path: Path) -> None:
    out_path = tmp_path / "wiki_timeline_gwb_public_bios_v1_rich.json"
    res = build_public_bios_timeline(
        raw_root=REPO_ROOT / "SensibLaw" / "demo" / "ingest" / "gwb" / "public_bios_v1" / "raw",
        out_path=out_path,
        max_docs=20,
        max_snippets_per_doc=12,
        snippet_chars=420,
    )
    assert res["ok"] is True
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["events"]
    assert len(payload["events"]) > 6
    texts = [str(row.get("text") or "") for row in payload["events"]]
    assert any("George W. Bush" in text for text in texts)
    assert any("Iraq" in text or "Supreme Court" in text or "signed" in text for text in texts)
