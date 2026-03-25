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
    assert any(row.get("speaker_label") for row in payload["procedural_overlay"]["hearing_acts"])
    assert payload["summary"]["procedural_overlay_candidate_count"] >= 1
    assert payload["procedural_move_overlay"]["selected_moves"]
    assert payload["summary"]["procedural_move_count"] >= payload["summary"]["procedural_move_selected_count"] >= 1
    assert any(row.get("speaker_label") for row in payload["procedural_move_overlay"]["selected_moves"])
    assert payload["event_assembly_overlay"]["selected_events"]
    assert payload["summary"]["assembled_event_count"] >= payload["summary"]["selected_event_count"] >= 1
    assert payload["summary"]["reviewed_event_projection_count"] >= payload["summary"]["selected_reviewed_event_count"] >= 1
    assert 0.0 <= payload["summary"]["reviewed_event_coverage_ratio"] <= 1.0
    assert payload["summary"]["reviewed_event_review_queue_count"] >= payload["reviewed_event_projection"]["selected_review_queue_count"]
    assert payload["summary"]["event_move_coverage_count"] >= 1
    assert payload["summary"]["event_move_coverage_ratio"] > 0.0
    assert payload["reviewed_event_projection"]["selected_reviewed_events"]
    assert payload["reviewed_event_projection"]["selected_review_queue"]
    assert any(
        row["hearing_act_kind"] in {"party_submission", "statutory_argument", "court_intervention", "bench_question"}
        for row in payload["procedural_overlay"]["selected_candidates"]
    )
    assert any(
        row["move_kind"] in {"party_submission", "statutory_argument", "court_intervention", "bench_question"}
        for row in payload["procedural_move_overlay"]["selected_moves"]
    )
    assert any(
        row["event_kind"] in {"bench_question_exchange", "bench_counsel_exchange", "bench_counsel_exchange_chain", "party_submission_sequence", "authority_argument_sequence", "authority_argument_cluster", "extended_authority_argument_cluster", "procedural_direction_event"}
        for row in payload["event_assembly_overlay"]["selected_events"]
    )
    assert any(
        "section_6k" in row.get("topic_tokens", [])
        for row in payload["event_assembly_overlay"]["selected_events"]
    ) or any(
        "section_6k" in row.get("topic_tokens", [])
        for row in payload["procedural_move_overlay"]["selected_moves"]
    )
    assert any(
        len(row.get("source_move_ids") or []) >= 1
        for row in payload["event_assembly_overlay"]["selected_events"]
    )
    assert any(
        row.get("speaker_labels")
        for row in payload["event_assembly_overlay"]["selected_events"]
    )
    assert any(
        row.get("review_rows")
        for row in payload["reviewed_event_projection"]["selected_reviewed_events"]
    )
    assert all(
        "score_breakdown" in row
        and {"event_score", "review_bonus", "fact_bonus", "provenance_bonus"} <= set(row["score_breakdown"].keys())
        for row in payload["reviewed_event_projection"]["selected_reviewed_events"]
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
    assert "event_assembly_overlay_finished" in stages
    assert "reviewed_event_projection_finished" in stages
    assert stages[-1] == "build_finished"


def test_build_au_transcript_dense_substrate_bench_counsel_pair_without_topic_overlap(tmp_path: Path) -> None:
    hearing_txt = tmp_path / "01_Hearing.txt"
    hearing_txt.write_text(
        "\n".join(
            [
                "TRANSCRIPT OF PROCEEDINGS",
                "GAGELER CJ: What now?",
                "MR P.D. HERZFELD, SC : Yes.",
                "GAGELER CJ: When is this finalised?",
                "MR P.D. HERZFELD, SC : It is not finalised yet.",
            ]
        ),
        encoding="utf-8",
    )

    result = build_dense_substrate(tmp_path / "out", transcript_paths=[hearing_txt])
    payload = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    selected_events = payload["event_assembly_overlay"]["selected_events"]
    event_kinds = {row["event_kind"] for row in selected_events}

    assert "bench_question_exchange" in event_kinds or "bench_counsel_exchange" in event_kinds or "bench_counsel_exchange_chain" in event_kinds
    assert any(
        row["event_kind"] in {"bench_question_exchange", "bench_counsel_exchange", "bench_counsel_exchange_chain"}
        and len(row.get("source_move_ids") or []) >= 2
        for row in selected_events
    )


def test_build_au_transcript_dense_substrate_assembles_exchange_chains(tmp_path: Path) -> None:
    hearing_txt = tmp_path / "01_Hearing.txt"
    hearing_txt.write_text(
        "\n".join(
            [
                "TRANSCRIPT OF PROCEEDINGS",
                "GAGELER CJ: What is your answer on section 6K?",
                "MR P.D. HERZFELD, SC : Our answer is that section 6K applies under the Civil Liability Act.",
                "GAGELER CJ: Why does that answer deal with the proper defendant question?",
                "MR P.D. HERZFELD, SC : We submit that the proper defendant point follows from the same section 6K argument.",
            ]
        ),
        encoding="utf-8",
    )

    result = build_dense_substrate(tmp_path / "out", transcript_paths=[hearing_txt])
    payload = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    event_kinds = {row["event_kind"] for row in payload["event_assembly_overlay"]["selected_events"]}

    assert "bench_counsel_exchange_chain" in event_kinds or "bench_counsel_exchange" in event_kinds
    assert any(
        row["event_kind"] == "bench_counsel_exchange_chain" and len(row.get("source_move_ids") or []) >= 3
        for row in payload["event_assembly_overlay"]["selected_events"]
    ) or any(
        row["event_kind"] == "bench_counsel_exchange" and len(row.get("source_move_ids") or []) >= 2
        for row in payload["event_assembly_overlay"]["selected_events"]
    )
    assert any(
        "section_6k" in row.get("topic_tokens", [])
        for row in payload["event_assembly_overlay"]["selected_events"]
    )
