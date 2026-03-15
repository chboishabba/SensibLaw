from __future__ import annotations

import json

from scripts.run_fact_review_acceptance_wave import main
from src.fact_intake import load_fact_review_acceptance_fixture_manifest


def test_wave1_acceptance_fixture_manifest_lists_canonical_real_and_synthetic_fixtures() -> None:
    manifest = load_fact_review_acceptance_fixture_manifest()
    fixture_ids = {row["fixture_id"] for row in manifest["fixtures"]}
    assert manifest["wave"] == "wave1_legal"
    assert {"real_transcript_intake_v1", "real_au_procedural_v1", "synthetic_sparse_dates_v1"} <= fixture_ids
    assert {row["fixture_kind"] for row in manifest["fixtures"]} == {"real", "synthetic"}


def test_wave2_acceptance_fixture_manifest_lists_balanced_fixtures() -> None:
    manifest = load_fact_review_acceptance_fixture_manifest(wave="wave2_balanced")
    fixture_ids = {row["fixture_id"] for row in manifest["fixtures"]}
    assert manifest["wave"] == "wave2_balanced"
    assert {"real_transcript_intake_v1", "synthetic_personal_fragments_v1", "synthetic_investigative_reopen_v1"} <= fixture_ids
    assert {row["fixture_kind"] for row in manifest["fixtures"]} == {"real", "synthetic"}


def test_wave3_trauma_acceptance_fixture_manifest_lists_canonical_fixtures() -> None:
    manifest = load_fact_review_acceptance_fixture_manifest(wave="wave3_trauma_advocacy")
    fixture_ids = {row["fixture_id"] for row in manifest["fixtures"]}
    assert manifest["wave"] == "wave3_trauma_advocacy"
    assert {"real_transcript_fragmented_support_v1", "synthetic_trauma_fragment_cluster_v1", "synthetic_support_worker_handoff_v1"} <= fixture_ids


def test_wave3_public_knowledge_manifest_lists_canonical_fixtures() -> None:
    manifest = load_fact_review_acceptance_fixture_manifest(wave="wave3_public_knowledge")
    fixture_ids = {row["fixture_id"] for row in manifest["fixtures"]}
    assert manifest["wave"] == "wave3_public_knowledge"
    assert {"real_gwb_contested_public_figure_v1", "synthetic_trump_public_figure_legality_v1", "synthetic_wikidata_claim_worker_v1"} <= fixture_ids


def test_wave4_family_law_manifest_lists_canonical_fixtures() -> None:
    manifest = load_fact_review_acceptance_fixture_manifest(wave="wave4_family_law")
    fixture_ids = {row["fixture_id"] for row in manifest["fixtures"]}
    assert manifest["wave"] == "wave4_family_law"
    assert {"synthetic_family_client_circumstances_v1", "synthetic_child_sensitive_context_v1", "synthetic_cross_side_handoff_v1"} <= fixture_ids


def test_wave4_medical_regulatory_manifest_lists_canonical_fixtures() -> None:
    manifest = load_fact_review_acceptance_fixture_manifest(wave="wave4_medical_regulatory")
    fixture_ids = {row["fixture_id"] for row in manifest["fixtures"]}
    assert manifest["wave"] == "wave4_medical_regulatory"
    assert {"synthetic_medical_negligence_review_v1", "synthetic_professional_discipline_record_v1", "synthetic_regulatory_public_drift_v1"} <= fixture_ids


def test_wave5_handoff_false_coherence_manifest_lists_canonical_fixtures() -> None:
    manifest = load_fact_review_acceptance_fixture_manifest(wave="wave5_handoff_false_coherence")
    fixture_ids = {row["fixture_id"] for row in manifest["fixtures"]}
    assert manifest["wave"] == "wave5_handoff_false_coherence"
    assert {
        "real_transcript_professional_handoff_v1",
        "real_transcript_false_coherence_v1",
        "synthetic_personal_professional_handoff_v1",
        "synthetic_multi_professional_reopen_v1",
        "synthetic_false_coherence_pressure_v1",
    } <= fixture_ids


def test_wave1_acceptance_runner_builds_fixture_batch_and_rollup(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--fixture-id",
            "real_transcript_intake_v1",
            "--fixture-id",
            "real_au_procedural_v1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["wave"] == "wave1_legal"
    assert payload["fixture_count"] == 2
    assert {row["fixture_id"] for row in payload["fixtures"]} == {"real_transcript_intake_v1", "real_au_procedural_v1"}
    assert any(row["story_id"] == "SL-US-12" for row in payload["stories"])
    assert all("source_label" in row for row in payload["fixtures"])


def test_wave2_acceptance_runner_builds_balanced_fixture_batch_and_rollup(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--wave",
            "wave2_balanced",
            "--fixture-id",
            "synthetic_personal_fragments_v1",
            "--fixture-id",
            "synthetic_investigative_reopen_v1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["wave"] == "wave2_balanced"
    assert payload["fixture_count"] == 2
    assert {row["fixture_id"] for row in payload["fixtures"]} == {"synthetic_personal_fragments_v1", "synthetic_investigative_reopen_v1"}
    assert any(row["story_id"] == "ITIR-US-11" for row in payload["stories"])
    assert any(row["story_id"] == "ITIR-US-12" for row in payload["stories"])


def test_wave3_trauma_acceptance_runner_builds_fixture_batch_and_rollup(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--wave",
            "wave3_trauma_advocacy",
            "--fixture-id",
            "synthetic_trauma_fragment_cluster_v1",
            "--fixture-id",
            "synthetic_support_worker_handoff_v1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["wave"] == "wave3_trauma_advocacy"
    assert {row["story_id"] for row in payload["stories"]} == {"ITIR-US-13", "ITIR-US-14"}


def test_wave3_public_knowledge_runner_builds_fixture_batch_and_rollup(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--wave",
            "wave3_public_knowledge",
            "--fixture-id",
            "synthetic_wikidata_claim_worker_v1",
            "--fixture-id",
            "synthetic_lawyer_maintainer_conflict_v1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["wave"] == "wave3_public_knowledge"
    assert any(row["story_id"] == "SL-US-16" for row in payload["stories"])
    assert any(row["story_id"] == "SL-US-24" for row in payload["stories"])


def test_wave4_family_law_runner_builds_fixture_batch_and_rollup(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--wave",
            "wave4_family_law",
            "--fixture-id",
            "synthetic_family_client_circumstances_v1",
            "--fixture-id",
            "synthetic_cross_side_handoff_v1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["wave"] == "wave4_family_law"
    assert any(row["story_id"] == "SL-US-25" for row in payload["stories"])
    assert any(row["story_id"] == "SL-US-28" for row in payload["stories"])


def test_wave4_medical_regulatory_runner_builds_fixture_batch_and_rollup(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--wave",
            "wave4_medical_regulatory",
            "--fixture-id",
            "synthetic_medical_negligence_review_v1",
            "--fixture-id",
            "synthetic_professional_discipline_record_v1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["wave"] == "wave4_medical_regulatory"
    assert any(row["story_id"] == "SL-US-29" for row in payload["stories"])
    assert any(row["story_id"] == "SL-US-30" for row in payload["stories"])


def test_wave5_handoff_false_coherence_runner_builds_fixture_batch_and_rollup(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--wave",
            "wave5_handoff_false_coherence",
            "--fixture-id",
            "synthetic_personal_professional_handoff_v1",
            "--fixture-id",
            "synthetic_false_coherence_pressure_v1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["wave"] == "wave5_handoff_false_coherence"
    assert any(row["story_id"] == "ITIR-US-15" for row in payload["stories"])
    assert any(row["story_id"] == "ITIR-US-16" for row in payload["stories"])


def test_wave1_acceptance_runner_reports_story_outcomes_and_gap_rollups(tmp_path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--fixture-id",
            "synthetic_sparse_dates_v1",
            "--fixture-id",
            "synthetic_assertion_outcome_v1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    story_rows = [story for fixture in payload["fixtures"] for story in fixture["stories"]]
    assert story_rows
    assert all(story["status"] in {"pass", "partial", "fail"} for story in story_rows)
    assert all("failed_check_ids" in story for story in story_rows)
    assert all("gap_tags" in story for story in story_rows)
