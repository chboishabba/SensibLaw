from __future__ import annotations

import json
from pathlib import Path

from scripts.build_gwb_broader_promotion_diagnostics import build_diagnostics


def test_build_gwb_broader_promotion_diagnostics(tmp_path: Path) -> None:
    res = build_diagnostics(tmp_path)
    payload = json.loads(Path(res["artifact_path"]).read_text(encoding="utf-8"))
    assert payload["summary"]["source_family_count"] == 2
    assert payload["source_family_summaries"]
    assert any(row["source_family"] == "public_bios_timeline" for row in payload["source_family_summaries"])
    assert any(row["source_family"] == "corpus_book_timeline" for row in payload["source_family_summaries"])
    assert payload["summary"]["families_with_matched_seed_support"] >= 1
    assert "core_reading" in payload["summary"]
