from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_affidavit_coverage_review import write_affidavit_coverage_review


def test_render_affidavit_plantuml_script_writes_dual_views(tmp_path: Path) -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "render_affidavit_plantuml_demo"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The witness attended the meeting on Tuesday.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": "The witness denied attending the second meeting.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            },
        ],
        "review_queue": [
            {
                "fact_id": "fact:f1",
                "contestation_count": 0,
                "reason_codes": [],
                "latest_review_status": "reviewed",
            },
            {
                "fact_id": "fact:f2",
                "contestation_count": 1,
                "reason_codes": ["source_conflict"],
                "latest_review_status": "contested",
            },
        ],
    }
    artifact = write_affidavit_coverage_review(
        output_dir=tmp_path / "artifact",
        source_payload=source_payload,
        affidavit_text=(
            "The witness attended the meeting on Tuesday.\n\n"
            "The witness denied attending the second meeting.\n\n"
            "The witness also saw the respondent leave at noon."
        ),
        source_path="bundle.json",
        affidavit_path="draft.txt",
    )

    output_dir = tmp_path / "plantuml"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_affidavit_plantuml.py",
            "--artifact-json",
            str(Path(artifact["artifact_path"])),
            "--output-dir",
            str(output_dir),
            "--stem",
            "demo_affidavit",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True

    resolution = output_dir / "demo_affidavit.resolution.puml"
    mechanical = output_dir / "demo_affidavit.mechanical.puml"
    assert resolution.exists()
    assert mechanical.exists()
    assert "Claim Resolution Graph" in resolution.read_text(encoding="utf-8")
    assert "Mechanical Parse Graph" in mechanical.read_text(encoding="utf-8")
