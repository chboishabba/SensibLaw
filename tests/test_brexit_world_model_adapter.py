from __future__ import annotations

import json
from pathlib import Path

from src.sources.national_archives.brexit_world_model_adapter import (
    BREXIT_REVIEW_WORLD_MODEL_SCHEMA_VERSION,
    build_brexit_review_world_model_report,
)


def test_build_brexit_review_world_model_report() -> None:
    payload = json.loads(
        Path("SensibLaw/tmp_out/gwb_broader_review_v1.json").read_text(encoding="utf-8")
    )

    report = build_brexit_review_world_model_report(payload)

    assert report["schema_version"] == BREXIT_REVIEW_WORLD_MODEL_SCHEMA_VERSION
    assert report["artifact_id"] == payload["normalized_metrics_v1"]["artifact_id"]
    assert report["lane_id"] == payload["promotion_gate"]["lane"]
    assert report["decision"] == payload["promotion_gate"]["decision"]
    assert report["summary"]["claim_count"] == len(report["claims"])
    assert report["summary"]["archive_claim_count"] == len(payload["archive_follow_rows"])
    assert report["summary"]["review_row_claim_count"] >= 1
    assert report["summary"]["must_review_count"] >= 1

    review_claim = next(
        claim for claim in report["claims"] if claim["claim_id"].startswith("brexit-review:")
    )
    assert review_claim["nat_claim"]["state_basis"] == "brexit_artifact"
    assert review_claim["nat_claim"]["property"] == "review_status"
    assert review_claim["convergence"]["normalized_sources"][0]["verification_status"] in {
        "covered",
        "missing_review",
        "review_required",
    }

    archive_claim = next(
        claim for claim in report["claims"] if claim["claim_id"].startswith("brexit-archive:")
    )
    assert archive_claim["nat_claim"]["property"] == "archive_follow_title"
    assert archive_claim["nat_claim"]["value"]
    assert archive_claim["action_policy"]["actionability"] == "must_review"
