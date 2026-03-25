from __future__ import annotations

import json
from pathlib import Path

from scripts.build_au_transcript_structural_checkpoint import build_checkpoint


def test_build_au_transcript_structural_checkpoint(tmp_path: Path) -> None:
    hearing_txt = tmp_path / "01_Hearing.txt"
    hearing_txt.write_text(
        "\n".join(
            [
                "AustLII Search",
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
                "- [00:00:07.100 --> 00:00:09.000] The court considers the proceeding.",
                "- [00:00:09.100 --> 00:00:11.000] The appeal concerns child abuse proceedings.",
            ]
        ),
        encoding="utf-8",
    )

    result = build_checkpoint(tmp_path / "out", transcript_paths=[hearing_txt, hearing_md])
    payload = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))

    assert payload["summary"]["source_file_count"] == 2
    assert payload["summary"]["unit_count"] >= 3
    assert payload["summary"]["selected_excerpt_count"] >= 1
    assert payload["selected_excerpts"]
    assert any("civil liability act" in " ".join(row["keyword_hits"]) for row in payload["selected_excerpts"])


def test_build_au_transcript_structural_checkpoint_reports_progress(tmp_path: Path) -> None:
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
            ]
        ),
        encoding="utf-8",
    )
    updates: list[tuple[str, dict[str, object]]] = []

    build_checkpoint(
        tmp_path / "out",
        transcript_paths=[hearing_txt, hearing_md],
        progress_callback=lambda stage, details: updates.append((stage, details)),
    )

    stages = [stage for stage, _ in updates]
    assert stages[0] == "build_started"
    assert "load_units_started" in stages
    assert "source_loaded" in stages
    assert "structure_report_finished" in stages
    assert "excerpt_selection_finished" in stages
    assert stages[-1] == "build_finished"
