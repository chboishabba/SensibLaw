from __future__ import annotations

import json
from pathlib import Path

from scripts.build_au_transcript_dense_substrate import build_dense_substrate


def test_build_au_transcript_dense_substrate(tmp_path: Path) -> None:
    hearing_txt = tmp_path / "01_Hearing.txt"
    hearing_txt.write_text(
        "\n".join(
            [
                "TRANSCRIPT OF PROCEEDINGS",
                "MR P.D. HERZFELD, SC : We rely on the Civil Liability Act and the duty of care issue.",
                "GAGELER CJ: Yes.",
                "MR J.T. GLEESON, SC : The respondent disputes the proper defendant point.",
            ]
        ),
        encoding="utf-8",
    )
    hearing_md = tmp_path / "hearing.md"
    hearing_md.write_text(
        "\n".join(
            [
                "# Transcript (demo, en-x-autogen)",
                "- [00:00:01.000 --> 00:00:03.000] The appellant relies on section 6K of the Civil Liability Act.",
                "- [00:00:03.100 --> 00:00:05.000] The respondent disputes the duty of care.",
                "- [00:00:05.100 --> 00:00:07.000] Counsel refers to the proper defendant issue.",
                "- [00:00:07.100 --> 00:00:09.000] The court considers the proceeding.",
                "- [00:00:09.100 --> 00:00:11.000] The appeal concerns child abuse proceedings.",
            ]
        ),
        encoding="utf-8",
    )

    result = build_dense_substrate(tmp_path / "out", transcript_paths=[hearing_txt, hearing_md])
    payload = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))

    assert payload["summary"]["source_file_count"] == 2
    assert payload["summary"]["fact_count"] >= payload["overlay_projection"]["selected_fact_count"] >= 1
    assert payload["summary"]["review_queue_count"] >= payload["overlay_projection"]["selected_review_queue_count"] >= 1
    assert payload["run"]["bundle_version"] == "fact.review.bundle.v1"
    assert payload["overlay_projection"]["selected_facts"]
    assert payload["summary"]["hearing_act_count"] >= payload["summary"]["procedural_overlay_candidate_count"] >= 1
    assert payload["procedural_overlay"]["selected_candidates"]
    assert payload["procedural_overlay"]["hearing_acts"]
    assert payload["summary"]["procedural_overlay_candidate_count"] >= 1
    assert payload["procedural_move_overlay"]["selected_moves"]
    assert payload["summary"]["procedural_move_count"] >= payload["summary"]["procedural_move_selected_count"] >= 1
    assert any(
        row["hearing_act_kind"] in {"party_submission", "statutory_argument", "court_intervention", "bench_question"}
        for row in payload["procedural_overlay"]["selected_candidates"]
    )
    assert any(
        row["move_kind"] in {"party_submission", "statutory_argument", "court_intervention", "bench_question"}
        for row in payload["procedural_move_overlay"]["selected_moves"]
    )
    assert any("civil liability act" in row["excerpt_preview"].casefold() for row in payload["overlay_projection"]["selected_facts"])


def test_build_au_transcript_dense_substrate_reports_progress(tmp_path: Path) -> None:
    hearing_txt = tmp_path / "01_Hearing.txt"
    hearing_txt.write_text(
        "\n".join(
            [
                "TRANSCRIPT OF PROCEEDINGS",
                "MR P.D. HERZFELD, SC : We rely on the Civil Liability Act and the duty of care issue.",
                "GAGELER CJ: Yes.",
            ]
        ),
        encoding="utf-8",
    )
    hearing_md = tmp_path / "hearing.md"
    hearing_md.write_text(
        "\n".join(
            [
                "# Transcript (demo, en-x-autogen)",
                "- [00:00:01.000 --> 00:00:03.000] The appellant relies on section 6K of the Civil Liability Act.",
                "- [00:00:03.100 --> 00:00:05.000] The respondent disputes the duty of care.",
                "- [00:00:05.100 --> 00:00:07.000] Counsel refers to the proper defendant issue.",
            ]
        ),
        encoding="utf-8",
    )
    updates: list[tuple[str, dict[str, object]]] = []

    build_dense_substrate(
        tmp_path / "out",
        transcript_paths=[hearing_txt, hearing_md],
        progress_callback=lambda stage, details: updates.append((stage, details)),
    )

    stages = [stage for stage, _ in updates]
    assert stages[0] == "build_started"
    assert "load_units_finished" in stages
    assert "semantic_pipeline_started" in stages
    assert "semantic_pipeline_finished" in stages
    assert "overlay_bundle_finished" in stages
    assert "overlay_projection_finished" in stages
    assert "procedural_overlay_finished" in stages
    assert "procedural_move_overlay_finished" in stages
    assert stages[-1] == "build_finished"
