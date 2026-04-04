from __future__ import annotations

import json
from pathlib import Path

from src.models.gwb_convergence import build_gwb_public_convergence


def test_gwb_public_convergence_builds_record() -> None:
    root = Path(__file__).resolve().parent
    slice_payload = json.loads(
        (root / "fixtures" / "zelph" / "gwb_public_handoff_v1" / "gwb_public_handoff_v1.slice.json").read_text(encoding="utf-8")
    )
    record = build_gwb_public_convergence(slice_payload)
    assert record["schema_version"].startswith("sl.world_model_convergence")
    assert record["claim_id"].startswith("gwb-public:")
    assert record["merged_evidence_basis"]["source_count"] >= 0
    assert isinstance(record["normalized_sources"], list)
