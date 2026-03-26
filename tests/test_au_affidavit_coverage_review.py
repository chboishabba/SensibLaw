from __future__ import annotations

import json
from pathlib import Path

from scripts.build_au_affidavit_coverage_review import build_au_affidavit_coverage_review


def test_build_au_affidavit_coverage_review(tmp_path: Path) -> None:
    result = build_au_affidavit_coverage_review(tmp_path / "out")

    artifact_path = Path(result["artifact_path"])
    summary_path = Path(result["summary_path"])
    assert artifact_path.exists()
    assert summary_path.exists()

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["version"] == "affidavit_coverage_review_v1"
    assert payload["source_input"]["source_kind"] == "au_checked_handoff_slice"
    assert payload["source_input"]["source_row_count"] == 3
    assert payload["summary"]["affidavit_proposition_count"] == 3
    assert payload["summary"]["covered_count"] >= 1
    assert payload["summary"]["partial_count"] == 0
    assert payload["summary"]["unsupported_affidavit_count"] >= 2
    assert payload["summary"]["missing_review_count"] >= 2
    assert payload["summary"]["affidavit_supported_ratio"] < 1.0
    assert any(row["coverage_status"] == "unsupported_affidavit" for row in payload["affidavit_rows"])
    assert any(row["review_status"] == "missing_review" for row in payload["source_review_rows"])
    assert "provenance-first comparison surface" in summary_path.read_text(encoding="utf-8")
