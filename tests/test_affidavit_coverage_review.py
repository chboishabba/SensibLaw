from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.fact_intake import build_contested_affidavit_proving_slice
from scripts.build_affidavit_coverage_review import (
    _classify_argumentative_role,
    _derive_claim_root_fields,
    _derive_relation_classification,
    _derive_primary_target_component,
    _derive_semantic_basis,
    _infer_response_packet,
    _score_proposition_against_source_row,
    _split_affidavit_text,
    _tokenize,
    build_affidavit_coverage_review,
    write_affidavit_coverage_review,
)


def test_build_affidavit_coverage_review_from_fact_review_bundle(tmp_path: Path) -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "au_semantic:test-run"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The applicant filed a complaint on 1 March 2024.",
                "candidate_status": "reviewed",
                "statement_ids": ["statement:s1"],
                "excerpt_ids": ["excerpt:e1"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": "The respondent denied the allegation in correspondence.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s2"],
                "excerpt_ids": ["excerpt:e2"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:f3",
                "fact_text": "A witness recalled seeing a blue car near the clinic.",
                "candidate_status": "abstained",
                "statement_ids": ["statement:s3"],
                "excerpt_ids": ["excerpt:e3"],
                "source_ids": ["src:2"],
            },
            {
                "fact_id": "fact:f4",
                "fact_text": "The hearing was adjourned to 5 March 2024.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s4"],
                "excerpt_ids": ["excerpt:e4"],
                "source_ids": ["src:2"],
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
            {
                "fact_id": "fact:f3",
                "contestation_count": 0,
                "reason_codes": ["statement_only_fact"],
                "latest_review_status": "abstained",
            },
            {
                "fact_id": "fact:f4",
                "contestation_count": 0,
                "reason_codes": ["missing_date"],
                "latest_review_status": "review_queue",
            },
        ],
    }
    affidavit_text = (
        "The applicant filed a complaint on 1 March 2024.\n\n"
        "The respondent denied the complaint in correspondence.\n\n"
        "The court ordered costs against the respondent."
    )

    payload = build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text=affidavit_text,
        source_path="source.json",
        affidavit_path="draft.txt",
    )

    assert payload["summary"]["affidavit_proposition_count"] == 3
    assert payload["summary"]["covered_count"] == 1
    assert payload["summary"]["contested_affidavit_count"] == 1
    assert payload["summary"]["unsupported_affidavit_count"] == 1
    assert payload["summary"]["missing_review_count"] == 1
    assert payload["summary"]["contested_source_count"] == 1
    assert payload["summary"]["abstained_source_count"] == 1
    assert payload["summary"]["semantic_basis_counts"]

    affidavit_rows = {row["proposition_id"]: row for row in payload["affidavit_rows"]}
    assert affidavit_rows["aff-prop:p1-s1"]["coverage_status"] == "covered"
    assert affidavit_rows["aff-prop:p2-s1"]["coverage_status"] == "contested_source"
    assert affidavit_rows["aff-prop:p3-s1"]["coverage_status"] == "unsupported_affidavit"

    source_rows = {row["source_row_id"]: row for row in payload["source_review_rows"]}
    assert source_rows["fact:f1"]["review_status"] == "covered"
    assert source_rows["fact:f2"]["review_status"] == "contested_source"
    assert source_rows["fact:f3"]["review_status"] == "abstained_source"
    assert source_rows["fact:f4"]["review_status"] == "missing_review"
    assert source_rows["fact:f4"]["workload_classes"] == ["chronology_gap"]
    assert source_rows["fact:f4"]["has_calendar_reference_hint"] is True
    assert source_rows["fact:f4"]["has_procedural_event_cue"] is True
    assert any(anchor["anchor_kind"] == "calendar_reference" for anchor in source_rows["fact:f4"]["candidate_anchors"])
    assert any(anchor["anchor_kind"] == "procedural_event_keywords" for anchor in source_rows["fact:f4"]["candidate_anchors"])
    assert source_rows["fact:f4"]["recommended_next_action"] == "promote existing event/date cues into structured anchors"
    assert any(
        row["source_row_id"] == "fact:f4" and row["anchor_kind"] == "calendar_reference"
        for row in payload["provisional_structured_anchors"]
    )
    assert all("priority_rank" in row and "priority_score" in row for row in payload["provisional_structured_anchors"])
    assert payload["provisional_anchor_bundles"][0]["source_row_id"] == "fact:f4"
    assert payload["provisional_anchor_bundles"][0]["anchor_count"] == 2
    normalized = payload["normalized_metrics_v1"]
    assert normalized["lane_family"] == "au"
    assert normalized["review_item_status_counts"] == {
        "accepted": 1,
        "review_required": 1,
        "held": 1,
    }
    assert normalized["source_status_counts"] == {
        "accepted": 1,
        "review_required": 1,
        "held": 2,
    }
    assert normalized["primary_workload_counts"]["event_or_time_pressure"] == 1
    assert normalized["workload_presence_counts"]["event_or_time_pressure"] == 1
    assert normalized["candidate_signal_count"] == 2
    assert normalized["provisional_queue_row_count"] == 2
    assert normalized["provisional_bundle_count"] == 1
    assert normalized["review_required_source_ratio"] == 0.25


def test_split_affidavit_text_splits_semicolon_clause_into_multiple_propositions() -> None:
    propositions = _split_affidavit_text(
        "In mid-November 2024, there was an incident where I was waiting for my support worker to arrive; as I came down the side of the house, I could hear Johl was on the phone."
    )
    assert [row["proposition_id"] for row in propositions] == ["aff-prop:p1-s1", "aff-prop:p1-s2"]
    assert propositions[0]["text"] == "In mid-November 2024, there was an incident where I was waiting for my support worker to arrive"
    assert propositions[1]["text"] == "as I came down the side of the house, I could hear Johl was on the phone."


def test_write_affidavit_coverage_review_outputs_files(tmp_path: Path) -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "transcript_semantic:demo"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The witness attended the meeting on Tuesday.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            }
        ],
        "review_queue": [
            {
                "fact_id": "fact:f1",
                "contestation_count": 0,
                "reason_codes": [],
                "latest_review_status": "review_queue",
            }
        ],
    }
    out_dir = tmp_path / "artifact"
    result = write_affidavit_coverage_review(
        output_dir=out_dir,
        source_payload=source_payload,
        affidavit_text="The witness attended the meeting on Tuesday.",
        source_path="bundle.json",
        affidavit_path="draft.txt",
    )

    artifact_path = Path(result["artifact_path"])
    summary_path = Path(result["summary_path"])
    assert artifact_path.exists()
    assert summary_path.exists()

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["version"] == "affidavit_coverage_review_v1"
    assert payload["summary"]["covered_count"] == 1
    assert payload["normalized_metrics_v1"]["review_item_status_counts"]["accepted"] == 1
    assert "provenance-first comparison surface" in summary_path.read_text(encoding="utf-8")
    assert "Normalized Metrics" in summary_path.read_text(encoding="utf-8")


def test_write_affidavit_coverage_review_can_persist_without_bulky_artifacts(tmp_path: Path) -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "transcript_semantic:sqlite_only"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The witness attended the meeting on Tuesday.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            }
        ],
        "review_queue": [
            {
                "fact_id": "fact:f1",
                "contestation_count": 0,
                "reason_codes": [],
                "latest_review_status": "review_queue",
            }
        ],
    }
    out_dir = tmp_path / "artifact"
    db_path = tmp_path / "itir.sqlite"
    result = write_affidavit_coverage_review(
        output_dir=out_dir,
        source_payload=source_payload,
        affidavit_text="The witness attended the meeting on Tuesday.",
        source_path="bundle.json",
        affidavit_path="draft.txt",
        db_path=db_path,
        write_artifacts=False,
    )

    assert "artifact_path" not in result
    assert "summary_path" not in result
    assert result["persist_summary"]["review_run_id"]
    assert not (out_dir / "affidavit_coverage_review_v1.json").exists()
    assert not (out_dir / "affidavit_coverage_review_v1.summary.md").exists()


def test_build_affidavit_coverage_review_reports_progress() -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "transcript_semantic:demo"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The witness attended the meeting on Tuesday.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            }
        ],
        "review_queue": [
            {
                "fact_id": "fact:f1",
                "contestation_count": 0,
                "reason_codes": [],
                "latest_review_status": "review_queue",
            }
        ],
    }
    seen: list[tuple[str, dict[str, object]]] = []

    build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text="The witness attended the meeting on Tuesday.",
        progress_callback=lambda stage, details: seen.append((stage, details)),
    )

    stages = [stage for stage, _ in seen]
    assert "build_started" in stages
    assert "source_rows_loaded" in stages
    assert "proposition_split_finished" in stages
    assert "proposition_matching_progress" in stages
    assert "proposition_matching_finished" in stages
    assert "source_review_rows_finished" in stages
    assert "build_finished" in stages


def test_build_affidavit_coverage_review_reports_trace() -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "transcript_semantic:demo"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The witness attended the meeting on Tuesday.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            }
        ],
        "review_queue": [
            {
                "fact_id": "fact:f1",
                "contestation_count": 0,
                "reason_codes": [],
                "latest_review_status": "review_queue",
            }
        ],
    }
    seen: list[tuple[str, dict[str, object]]] = []

    build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text="The witness attended the meeting on Tuesday.",
        trace_callback=lambda stage, details: seen.append((stage, details)),
        trace_level="verbose",
    )

    stages = [stage for stage, _ in seen]
    assert "proposition_started" in stages
    assert "proposition_tokenized" in stages
    assert "proposition_top_candidates" in stages
    assert "response_packet_inferred" in stages
    assert "proposition_classified" in stages
    assert "semantic_basis_derived" in stages
    assert "promotion_result" in stages


def test_write_affidavit_coverage_review_persists_normalized_receiver(tmp_path: Path) -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "transcript_semantic:demo"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The witness attended the meeting on Tuesday.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            }
        ],
        "review_queue": [
            {
                "fact_id": "fact:f1",
                "contestation_count": 0,
                "reason_codes": [],
                "latest_review_status": "review_queue",
            }
        ],
    }
    out_dir = tmp_path / "artifact"
    db_path = tmp_path / "itir.sqlite"
    result = write_affidavit_coverage_review(
        output_dir=out_dir,
        source_payload=source_payload,
        affidavit_text="The witness attended the meeting on Tuesday.",
        source_path="bundle.json",
        affidavit_path="draft.txt",
        db_path=db_path,
    )

    persist_summary = result["persist_summary"]
    assert persist_summary["review_run_id"].startswith("contested_review:")
    assert persist_summary["affidavit_row_count"] == 1
    assert persist_summary["source_row_count"] == 1
    with sqlite3.connect(str(db_path)) as conn:
        run_row = conn.execute(
            "SELECT artifact_version, source_label, covered_count FROM contested_review_runs WHERE review_run_id = ?",
            (persist_summary["review_run_id"],),
        ).fetchone()
        assert run_row == ("affidavit_coverage_review_v1", "transcript_semantic:demo", 1)
        affidavit_row = conn.execute(
            "SELECT proposition_id, coverage_status, semantic_basis, promotion_status, relation_root, relation_leaf, primary_target_component, explanation_json, missing_dimensions_json FROM contested_review_affidavit_rows WHERE review_run_id = ?",
            (persist_summary["review_run_id"],),
        ).fetchone()
        assert affidavit_row[0] == "aff-prop:p1-s1"
        assert affidavit_row[1] == "covered"
        assert affidavit_row[2] == "structural"
        assert affidavit_row[3] in {"promoted_true", "promoted_false", "candidate_conflict", "abstained"}
        assert affidavit_row[4] == "supports"
        assert affidavit_row[5] in {"exact_support", "equivalent_support"}
    assert json.loads(affidavit_row[7])["classification"] == "supported"
    assert isinstance(json.loads(affidavit_row[8]), list)


def test_build_contested_affidavit_proving_slice_groups_rows_and_next_steps(tmp_path: Path) -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "proving_slice_demo"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The applicant filed a complaint on 1 March 2024.",
                "candidate_status": "reviewed",
                "statement_ids": ["statement:s1"],
                "excerpt_ids": ["excerpt:e1"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": "The respondent denied the allegation in correspondence.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s2"],
                "excerpt_ids": ["excerpt:e2"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:f3",
                "fact_text": "A witness recalled seeing a blue car near the clinic.",
                "candidate_status": "abstained",
                "statement_ids": ["statement:s3"],
                "excerpt_ids": ["excerpt:e3"],
                "source_ids": ["src:2"],
            },
            {
                "fact_id": "fact:f4",
                "fact_text": "The hearing was adjourned to 5 March 2024.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s4"],
                "excerpt_ids": ["excerpt:e4"],
                "source_ids": ["src:2"],
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
            {
                "fact_id": "fact:f3",
                "contestation_count": 0,
                "reason_codes": ["statement_only_fact"],
                "latest_review_status": "abstained",
            },
            {
                "fact_id": "fact:f4",
                "contestation_count": 0,
                "reason_codes": ["missing_date"],
                "latest_review_status": "review_queue",
            },
        ],
    }
    result = write_affidavit_coverage_review(
        output_dir=tmp_path / "artifact",
        source_payload=source_payload,
        affidavit_text=(
            "The applicant filed a complaint on 1 March 2024.\n\n"
            "The respondent denied the complaint in correspondence.\n\n"
            "The court ordered costs against the respondent."
        ),
        source_path="bundle.json",
        affidavit_path="draft.txt",
        db_path=tmp_path / "itir.sqlite",
    )

    with sqlite3.connect(str(tmp_path / "itir.sqlite")) as conn:
        proving_slice = build_contested_affidavit_proving_slice(
            conn,
            review_run_id=result["persist_summary"]["review_run_id"],
        )

    assert proving_slice["summary"]["supported_affidavit_count"] == 1
    assert proving_slice["summary"]["disputed_affidavit_count"] == 1
    assert proving_slice["summary"]["weakly_addressed_affidavit_count"] == 0
    assert proving_slice["summary"]["missing_affidavit_count"] == 1
    assert proving_slice["summary"]["needs_clarification_source_row_count"] == 2
    assert proving_slice["sections"]["supported"][0]["proposition_id"] == "aff-prop:p1-s1"
    assert proving_slice["sections"]["supported"][0]["relation_root"] == "supports"
    assert proving_slice["sections"]["supported"][0]["relation_leaf"] in {"exact_support", "equivalent_support"}
    assert proving_slice["sections"]["disputed"][0]["proposition_id"] == "aff-prop:p2-s1"
    assert proving_slice["sections"]["disputed"][0]["relation_root"] == "invalidates"
    assert proving_slice["sections"]["disputed"][0]["relation_leaf"] in {"explicit_dispute", "implicit_dispute"}
    assert proving_slice["sections"]["missing"][0]["proposition_id"] == "aff-prop:p3-s1"
    assert proving_slice["sections"]["missing"][0]["explanation"]["classification"] == "missing"
    assert proving_slice["source_attention"]["needs_clarification"][0]["source_row_id"] == "fact:f3"
    assert proving_slice["next_steps"][0]["step_id"] == "review_unsupported_affidavit"


def test_build_contested_affidavit_proving_slice_reclassifies_roles_without_inflating_supported(tmp_path: Path) -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "proving_slice_role_reclass_demo"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "I dispute that I did not respect John's wishes regarding his legal and other matters.",
                "candidate_status": "candidate",
                "statement_ids": [],
                "excerpt_ids": [],
                "source_ids": [],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": (
                    "This is a true fact regarding my ability to listen to conversations, insofar as all of John's "
                    "phone calls are automatically recorded."
                ),
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
                "latest_review_status": "review_queue",
            },
            {
                "fact_id": "fact:f2",
                "contestation_count": 0,
                "reason_codes": [],
                "latest_review_status": "review_queue",
            },
        ],
    }
    result = write_affidavit_coverage_review(
        output_dir=tmp_path / "artifact",
        source_payload=source_payload,
        affidavit_text=(
            "Johl would often not respect my wishes regarding my legal matter, and I felt he interfered and intervened without consideration and without much discussion.\n\n"
            "Examples of this behaviour include that Johl had access to all my emails and could listen to all conversations I had with other people that were recorded."
        ),
        source_path="bundle.json",
        affidavit_path="draft.txt",
        db_path=tmp_path / "itir.sqlite",
    )

    with sqlite3.connect(str(tmp_path / "itir.sqlite")) as conn:
        proving_slice = build_contested_affidavit_proving_slice(
            conn,
            review_run_id=result["persist_summary"]["review_run_id"],
        )

    assert proving_slice["summary"]["supported_affidavit_count"] == 0
    assert proving_slice["summary"]["disputed_affidavit_count"] == 1
    assert proving_slice["summary"]["non_substantive_response_affidavit_count"] == 1
    assert proving_slice["summary"]["weakly_addressed_affidavit_count"] == 0
    assert proving_slice["summary"]["missing_affidavit_count"] == 0
    assert proving_slice["sections"]["disputed"][0]["best_response_role"] == "dispute"
    non_substantive = proving_slice["sections"]["non_substantive_response"][0]
    assert non_substantive["support_status"] in {"responsive_but_non_substantive", "textually_addressed"}
    assert non_substantive["relation_root"] == "non_resolving"
    assert non_substantive["relation_leaf"] == "non_substantive_response"
    assert non_substantive["explanation"]["classification"] == "non_substantive_response"


def test_build_affidavit_coverage_review_uses_segment_level_matching_for_long_source_rows() -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "au_semantic:segment-match"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": (
                    "Counsel opened the submissions. Starting with the duty of care, may we emphasise at once "
                    "the significant effect of the Civil Liability Act on that question. Counsel then turned "
                    "to section 6I."
                ),
                "candidate_status": "candidate",
                "statement_ids": ["statement:s1"],
                "excerpt_ids": ["excerpt:e1"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": "The court adjourned until Tuesday morning.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s2"],
                "excerpt_ids": ["excerpt:e2"],
                "source_ids": ["src:1"],
            },
        ],
        "review_queue": [
            {"fact_id": "fact:f1", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"},
            {"fact_id": "fact:f2", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"},
        ],
    }

    payload = build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text="Starting with the duty of care, may we emphasize at once the significant effect of the Civil Liability Act on that question.",
    )

    affidavit_row = payload["affidavit_rows"][0]
    assert affidavit_row["coverage_status"] == "covered"
    assert affidavit_row["best_source_row_id"] == "fact:f1"
    assert affidavit_row["best_match_basis"] == "segment"
    assert "Starting with the duty of care" in affidavit_row["best_match_excerpt"]

    source_rows = {row["source_row_id"]: row for row in payload["source_review_rows"]}
    assert source_rows["fact:f1"]["review_status"] == "covered"
    assert source_rows["fact:f1"]["best_match_basis"] == "segment"
    assert source_rows["fact:f1"]["has_procedural_event_cue"] is True
    assert source_rows["fact:f2"]["review_status"] == "missing_review"


def test_build_affidavit_coverage_review_groups_related_uncovered_rows_by_proposition() -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "au_semantic:related-cluster"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The court dismissed the appeal and ordered indemnity costs against the applicant.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s1"],
                "excerpt_ids": ["excerpt:e1"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": "The appeal was dismissed with costs after the hearing ended.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s2"],
                "excerpt_ids": ["excerpt:e2"],
                "source_ids": ["src:1"],
            },
        ],
        "review_queue": [
            {
                "fact_id": "fact:f1",
                "contestation_count": 0,
                "reason_codes": ["missing_date"],
                "latest_review_status": "review_queue",
            },
            {
                "fact_id": "fact:f2",
                "contestation_count": 0,
                "reason_codes": ["statement_only_fact"],
                "latest_review_status": "review_queue",
            },
        ],
    }

    payload = build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text="The court dismissed the appeal with indemnity costs.",
    )

    assert payload["summary"]["covered_count"] == 1
    assert payload["summary"]["related_source_count"] == 1
    assert payload["summary"]["related_review_cluster_count"] == 1
    clusters = payload["related_review_clusters"]
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["proposition_id"] == "aff-prop:p1-s1"
    assert cluster["candidate_source_count"] == 1
    assert cluster["dominant_workload_class"] == "evidence_gap"
    assert cluster["recommended_next_action"] == "operator evidentiary review"
    assert cluster["reason_code_rollup"] == [{"reason_code": "statement_only_fact", "count": 1}]
    assert cluster["workload_class_rollup"] == [{"workload_class": "evidence_gap", "count": 1}]
    assert cluster["candidate_anchor_rollup"] == [{"anchor_kind": "procedural_event_keywords", "count": 1}]
    assert cluster["candidate_source_rows"][0]["source_row_id"] == "fact:f2"
    assert cluster["candidate_source_rows"][0]["primary_workload_class"] == "evidence_gap"
    assert payload["summary"]["provisional_structured_anchor_count"] == 1
    assert payload["summary"]["provisional_anchor_bundle_count"] == 1
    assert payload["provisional_structured_anchors"][0]["priority_rank"] == 1


def test_build_affidavit_coverage_review_downgrades_pure_restatement_from_covered() -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "au_semantic:restatement", "comparison_mode": "contested_narrative"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "The respondent cut off my internet in November 2024.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s1"],
                "excerpt_ids": ["excerpt:e1"],
                "source_ids": ["src:1"],
            }
        ],
        "review_queue": [
            {"fact_id": "fact:f1", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"},
        ],
    }

    payload = build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text="The respondent cut off my internet in November 2024.",
    )

    affidavit_row = payload["affidavit_rows"][0]
    assert affidavit_row["coverage_status"] in {"partial", "covered"}
    assert affidavit_row["best_response_role"] == "restatement_only"
    assert affidavit_row["best_adjusted_match_score"] < 0.6
    assert affidavit_row["matched_source_rows"][0]["response_role"] == "restatement_only"

    source_row = payload["source_review_rows"][0]
    assert source_row["review_status"] == "missing_review"
    assert source_row["best_response_role"] == "restatement_only"


def test_build_affidavit_coverage_review_keeps_adjusted_duplicate_root_row_in_ranking() -> None:
    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "au_semantic:duplicate-root-adjusted", "comparison_mode": "contested_narrative"},
        "facts": [
            {
                "fact_id": "fact:audio",
                "fact_text": (
                    "Johl came into my room and would turn off or stop what I was listening to on my computer. "
                    "I acknowledge this likely occurred on many occasions."
                ),
                "candidate_status": "candidate",
                "statement_ids": ["statement:s1"],
                "excerpt_ids": ["excerpt:e1"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:keyboard",
                "fact_text": "Johl came into my room and pulled out the keyboard so I couldn't type.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s2"],
                "excerpt_ids": ["excerpt:e2"],
                "source_ids": ["src:1"],
            },
        ],
        "review_queue": [
            {"fact_id": "fact:audio", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"},
            {"fact_id": "fact:keyboard", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"},
        ],
    }

    payload = build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text="Johl came into my room and would turn off or stop what I was listening to on my computer.",
    )

    affidavit_row = payload["affidavit_rows"][0]
    assert affidavit_row["best_source_row_id"] == "fact:audio"
    assert affidavit_row["duplicate_match_excerpt"] == "Johl came into my room and would turn off or stop what I was listening to on my computer."


def test_build_affidavit_coverage_review_promotes_duplicate_root_support_over_context_swap(monkeypatch) -> None:
    from scripts import build_affidavit_coverage_review as module

    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "au_semantic:duplicate-root", "comparison_mode": "contested_narrative"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "I cut off the internet in November 2024 as a final attempt to prompt a discussion to resolve the situation.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s1"],
                "excerpt_ids": ["excerpt:e1"],
                "source_ids": ["src:1"],
            },
            {
                "fact_id": "fact:f2",
                "fact_text": "The respondent cut off my internet in November 2024.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s2"],
                "excerpt_ids": ["excerpt:e2"],
                "source_ids": ["src:1"],
            }
        ],
        "review_queue": [
            {"fact_id": "fact:f1", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"},
            {"fact_id": "fact:f2", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"},
        ],
    }

    def fake_score(proposition, source_row):
        if source_row["source_row_id"] == "fact:f1":
            return {
                "score": 0.55,
                "adjusted_score": 0.60,
                "match_basis": "segment",
                "match_excerpt": "I cut off the internet in November 2024 as a final attempt to prompt a discussion to resolve the situation.",
                "duplicate_match_excerpt": None,
                "response_role": "dispute",
                "response_cues": [],
                "is_duplicate_excerpt": False,
            }
        return {
            "score": 0.52,
            "adjusted_score": 0.52,
            "match_basis": "segment",
            "match_excerpt": "The respondent cut off my internet in November 2024.",
            "duplicate_match_excerpt": None,
            "response_role": "restatement_only",
            "response_cues": [],
            "is_duplicate_excerpt": True,
        }

    monkeypatch.setattr(module, "_score_proposition_against_source_row", fake_score)

    payload = module.build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text="The respondent cut off my internet in November 2024.",
    )

    affidavit_row = payload["affidavit_rows"][0]
    assert affidavit_row["coverage_status"] == "covered"
    assert affidavit_row["duplicate_match_excerpt"] == "The respondent cut off my internet in November 2024."
    assert affidavit_row["relation_root"] == "supports"
    assert affidavit_row["relation_leaf"] == "equivalent_support"
    assert affidavit_row["claim_root_basis"] == "duplicate_excerpt"
    assert affidavit_row["claim_root_text"] == "The respondent cut off my internet in November 2024."
    assert affidavit_row["alternate_context_excerpt"] == "I cut off the internet in November 2024 as a final attempt to prompt a discussion to resolve the situation."
    assert affidavit_row["explanation"]["classification"] == "supported"
    assert affidavit_row["explanation"]["matched_response"] == "The respondent cut off my internet in November 2024."
    assert affidavit_row["missing_dimensions"] == []


def test_build_affidavit_coverage_review_marks_dispute_as_substantive_response(monkeypatch) -> None:
    from scripts import build_affidavit_coverage_review as module

    source_payload = {
        "version": "fact.review.bundle.v1",
        "run": {"source_label": "au_semantic:dispute", "comparison_mode": "contested_narrative"},
        "facts": [
            {
                "fact_id": "fact:f1",
                "fact_text": "I dispute that I cut off the internet in November 2024 because it was a router outage.",
                "candidate_status": "candidate",
                "statement_ids": ["statement:s1"],
                "excerpt_ids": ["excerpt:e1"],
                "source_ids": ["src:1"],
            }
        ],
        "review_queue": [
            {"fact_id": "fact:f1", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"},
        ],
    }

    monkeypatch.setattr(
        module,
        "_analyze_structural_sentence",
        lambda text: {
            "subject_texts": ["I"],
            "verb_lemmas": ["dispute"],
            "has_negation": True if "dispute" in text.casefold() else False,
            "has_first_person_subject": True,
            "has_hedge_verb": False,
        },
    )

    payload = module.build_affidavit_coverage_review(
        source_payload=source_payload,
        affidavit_text="The respondent cut off my internet in November 2024.",
    )

    affidavit_row = payload["affidavit_rows"][0]
    assert affidavit_row["coverage_status"] == "covered"
    assert affidavit_row["best_response_role"] == "dispute"
    assert "structural:negation" in affidavit_row["best_response_cues"]
    assert affidavit_row["best_adjusted_match_score"] >= affidavit_row["best_match_score"]

    source_row = payload["source_review_rows"][0]
    assert source_row["review_status"] == "covered"
    assert source_row["best_response_role"] == "dispute"


def test_hedged_denial_is_not_treated_as_admission(monkeypatch) -> None:
    from scripts import build_affidavit_coverage_review as module

    proposition = (
        "During that period, I feel that Johl engaged in behaviours that were coercive, "
        "controlling, intimidating, and on one occasion physically abusive."
    )
    excerpt = "I do not feel I did such in a controlling, coercive, or other similar manner that could intimidate or likewise."

    monkeypatch.setattr(
        module,
        "_analyze_structural_sentence",
        lambda text: {
            "subject_texts": ["I"],
            "verb_lemmas": ["feel"],
            "has_negation": True,
            "has_first_person_subject": True,
            "has_hedge_verb": True,
        },
    )

    role = module._classify_argumentative_role(proposition, excerpt, excerpt, use_row_fallback=False)
    packet = _infer_response_packet(
        proposition_text=proposition,
        best_match_excerpt=excerpt,
        duplicate_match_excerpt=None,
        response_role=role["response_role"],
        response_cues=role["response_cues"],
        coverage_status="partial",
    )

    assert role["response_role"] == "hedged_denial"
    assert "hedged_denial" in packet["response_acts"]
    assert "deny_characterisation" in packet["response_acts"]
    assert "hedged_denial_signal" in packet["legal_significance_signals"]
    assert "characterization_dispute" in packet["legal_significance_signals"]
    response = module.build_affidavit_coverage_review(
        source_payload={
            "version": "fact.review.bundle.v1",
            "run": {"source_label": "au_semantic:hedged", "comparison_mode": "contested_narrative"},
            "facts": [{"fact_id": "fact:f1", "fact_text": excerpt, "candidate_status": "candidate", "statement_ids": [], "excerpt_ids": [], "source_ids": []}],
            "review_queue": [{"fact_id": "fact:f1", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"}],
        },
        affidavit_text=proposition,
    )["affidavit_rows"][0]["response"]
    assert response["speech_act"] == "deny"
    assert "hedged" in response["modifiers"]


def test_low_overlap_explanation_like_text_stays_non_substantive() -> None:
    proposition = "I had no privacy at all while he had an expectation of privacy around some of his own communication."
    excerpt = "While some greater degree of urgency may have motivated my actions at some time."

    role = _classify_argumentative_role(proposition, excerpt, excerpt, use_row_fallback=False)
    packet = _infer_response_packet(
        proposition_text=proposition,
        best_match_excerpt=excerpt,
        duplicate_match_excerpt=None,
        response_role=role["response_role"],
        response_cues=role["response_cues"],
        coverage_status="partial",
    )

    assert role["response_role"] in {"non_response", "procedural_frame"}
    assert packet["response_acts"] in (["non_response"], ["procedural_or_nonresponsive_frame"])
    response = build_affidavit_coverage_review(
        source_payload={
            "version": "fact.review.bundle.v1",
            "run": {"source_label": "au_semantic:non-response", "comparison_mode": "contested_narrative"},
            "facts": [{"fact_id": "fact:f1", "fact_text": excerpt, "candidate_status": "candidate", "statement_ids": [], "excerpt_ids": [], "source_ids": []}],
            "review_queue": [{"fact_id": "fact:f1", "contestation_count": 0, "reason_codes": [], "latest_review_status": "review_queue"}],
        },
        affidavit_text=proposition,
    )["affidavit_rows"][0]["response"]
    assert response["speech_act"] == "other"
    assert set(response["modifiers"]) <= {"non_responsive", "repetition"}


def test_structural_negated_hedge_promotes_hedged_denial(monkeypatch) -> None:
    from scripts import build_affidavit_coverage_review as module

    monkeypatch.setattr(
        module,
        "_analyze_structural_sentence",
        lambda text: {
            "subject_texts": ["I"],
            "verb_lemmas": ["feel"],
            "has_negation": True,
            "has_first_person_subject": True,
            "has_hedge_verb": True,
        },
    )

    role = module._classify_argumentative_role(
        "The respondent cut off my internet in November 2024.",
        "I do not feel I did such.",
        "I do not feel I did such.",
        use_row_fallback=False,
    )

    assert role["response_role"] == "hedged_denial"
    assert role["response_cues"] == ["structural:negated_hedge"]


def test_duplicate_root_relation_prefers_support_over_contextual_dispute() -> None:
    relation = _derive_relation_classification(
        coverage_status="partial",
        support_status="responsive_but_non_substantive",
        conflict_state="disputed",
        support_direction="against",
        best_response_role="dispute",
        primary_target_component="predicate_text",
        best_match_excerpt="I cut off the internet in November 2024 as a final attempt to prompt a discussion to resolve the situation.",
        duplicate_match_excerpt="The respondent cut off my internet in November 2024.",
        alternate_context_excerpt="I cut off the internet in November 2024 as a final attempt to prompt a discussion to resolve the situation.",
    )

    assert relation["relation_root"] == "supports"
    assert relation["relation_leaf"] == "equivalent_support"
    assert relation["explanation"]["classification"] == "supported"
    assert relation["explanation"]["matched_response"] == "The respondent cut off my internet in November 2024."
    assert relation["missing_dimensions"] == []


def test_derive_claim_root_fields_preserves_duplicate_root_and_context() -> None:
    root = _derive_claim_root_fields(
        proposition_text="The respondent cut off my internet in November 2024.",
        duplicate_match_excerpt="The respondent cut off my internet in November 2024.",
        best_match_excerpt="I cut off the internet in November 2024 as a final attempt to prompt a discussion to resolve the situation.",
    )

    assert root["claim_root_basis"] == "duplicate_excerpt"
    assert root["claim_root_text"] == "The respondent cut off my internet in November 2024."
    assert root["claim_root_id"].startswith("claim_root:")
    assert root["alternate_context_excerpt"] == "I cut off the internet in November 2024 as a final attempt to prompt a discussion to resolve the situation."


def test_primary_target_component_prefers_characterization_over_predicate() -> None:
    target = _derive_primary_target_component(
        response={"component_targets": ["predicate_text", "characterization"]},
        response_acts=["deny_characterisation"],
    )
    assert target == "characterization"


def test_semantic_basis_becomes_mixed_for_structured_binding_plus_heuristic_justification() -> None:
    basis = _derive_semantic_basis(
        response_cues=[],
        response={"speech_act": "other"},
        response_component_bindings=[
            {
                "component": "time",
                "binding_kind": "time_alignment",
                "claim_span": {"text": "November 2024"},
                "response_span": {"text": "November 2024"},
            }
        ],
        justifications=[{"type": "consent"}],
    )
    assert basis == "mixed"


def test_semantic_basis_becomes_structural_for_predicate_binding_without_heuristics() -> None:
    basis = _derive_semantic_basis(
        response_cues=[],
        response={"speech_act": "deny"},
        response_component_bindings=[
            {
                "component": "predicate_text",
                "binding_kind": "predicate_overlap",
                "claim_span": {"text": "cut off my internet"},
                "response_span": {"text": "cut off my access to the internet"},
            }
        ],
        justifications=[],
    )
    assert basis == "structural"


def test_score_proposition_prefers_non_echo_sibling_over_echo_header() -> None:
    proposition = {"text": "Due to concerns that conversation may escalate I didn't want to come out of my room."}
    source_row = {
        "text": (
            "Due to concerns that conversation may escalate I didn't want to come out of my room. "
            "I turned off the internet to prompt a safe conversation about housing."
        ),
        "source_row_id": "fact:test-echo-row",
        "comparison_mode": "contested_narrative",
    }

    result = _score_proposition_against_source_row(proposition, source_row)

    assert result["match_excerpt"] == "I turned off the internet to prompt a safe conversation about housing."
    assert "Due to concerns that conversation may escalate I didn't want to come out of my room" in (result["duplicate_match_excerpt"] or "")
    assert result["is_proposition_echo"] is False


def test_score_proposition_prefers_numbered_rebuttal_over_echo_preamble_clause() -> None:
    proposition = {"text": "Due to concerns that conversation may escalate I didn't want to come out of my room."}
    source_row = {
        "text": (
            "In mid-November 2024 Johl cut off my access to the internet. "
            "I think it was due to the fact that he had come to my door and wanted me to come out and talk to him. "
            "Due to concerns that conversation may escalate I didn't want to come out of my room. "
            "1. Communication had broken down. "
            "4. After consecutive attempts on my behalf to resolve our misunderstandings, "
            "and in lieu of the constant stream of accusations, I disabled John's internet "
            "as a final attempt to prompt a discussion to resolve the situation."
        ),
        "source_row_id": "fact:test-numbered-rebuttal-row",
        "comparison_mode": "contested_narrative",
    }

    result = _score_proposition_against_source_row(proposition, source_row)

    assert result["match_excerpt"] == "After consecutive attempts on my behalf to resolve our misunderstandings"
    assert "Due to concerns that conversation may escalate I didn't want to come out of my room" in (result["duplicate_match_excerpt"] or "")


def test_score_proposition_promotes_quote_rebuttal_acknowledgement_over_echo_header() -> None:
    proposition = {"text": "Johl came into my room and would turn off or stop what I was listening to on my computer."}
    source_row = {
        "text": (
            "Johl came into my room and would turn off or stop what I was listening to on my computer. "
            "I acknowledge this likely occurred on many occasions, and on some occasions, "
            "John would express his discontent. I acknowledge that I may have done this more urgently on some occasions than others."
        ),
        "source_row_id": "fact:test-ack-row",
        "comparison_mode": "contested_narrative",
    }

    result = _score_proposition_against_source_row(proposition, source_row)

    assert result["match_basis"] == "clause"
    assert result["match_excerpt"] == "I acknowledge this likely occurred on many occasions"
    assert result["response_role"] == "support_or_corroboration"
    assert "Johl came into my room and would turn off or stop what I was listening to on my computer" in (result["duplicate_match_excerpt"] or "")


def test_score_proposition_prefers_keyboard_rebuttal_over_audio_echo_family() -> None:
    proposition = {"text": "Johl came into my room and pulled out the keyboard so I couldn’t type."}
    source_row = {
        "text": (
            "Johl came into my room and pulled out the keyboard so I couldn't type. "
            "John insisted on minimising my feelings and needs, and so, for my own sanity, "
            "I was forced to remove the keyboard to prevent further disagreements."
        ),
        "source_row_id": "fact:test-keyboard-row",
        "comparison_mode": "contested_narrative",
    }

    result = _score_proposition_against_source_row(proposition, source_row)

    assert result["match_basis"] == "clause"
    assert result["match_excerpt"] == "for my own sanity, I was forced to remove the keyboard to prevent further disagreements."
    assert result["predicate_alignment_score"] > 0.3
    assert result["adjusted_score"] > result["score"]


def test_score_proposition_prefers_epoa_rebuttal_over_generic_august_procedural_row() -> None:
    proposition = {"text": "In August 2024, I took steps to revoke my EPOA."}
    source_row = {
        "text": (
            "In August 2024 I took steps to revoke my EPOA. "
            "For a number of weeks and months, John had failed to complete the necessary steps to revoke his EPOA, while stating that he had done so. "
            "This is corroborated by the dated signature on the revocation documents."
        ),
        "source_row_id": "fact:test-epoa-row",
        "comparison_mode": "contested_narrative",
    }

    result = _score_proposition_against_source_row(proposition, source_row)

    assert result["match_excerpt"] == "For a number of weeks and months, John had failed to complete the necessary steps to revoke his EPOA"
    assert result["adjusted_score"] > result["score"]


def test_score_proposition_prefers_audio_family_row_over_keyboard_sibling_row() -> None:
    proposition = {"text": "Johl came into my room and would turn off or stop what I was listening to on my computer."}
    proposition["tokens"] = sorted(_tokenize(proposition["text"]))
    audio_row = {
        "text": (
            "Johl came into my room and would turn off or stop what I was listening to on my computer. "
            "I acknowledge this likely occurred on many occasions."
        ),
        "source_row_id": "fact:test-audio-row",
        "comparison_mode": "contested_narrative",
    }
    keyboard_row = {
        "text": (
            "Johl came into my room and pulled out the keyboard so I couldn't type. "
            "This incident occurred approximately one year prior to the alleged timeframe."
        ),
        "source_row_id": "fact:test-keyboard-row",
        "comparison_mode": "contested_narrative",
    }

    audio_score = _score_proposition_against_source_row(proposition, audio_row)
    keyboard_score = _score_proposition_against_source_row(proposition, keyboard_row)

    assert audio_score["adjusted_score"] > keyboard_score["adjusted_score"]


def test_score_proposition_does_not_treat_passive_listening_sentence_as_audio_control_family() -> None:
    proposition = {"text": "Johl came into my room and would turn off or stop what I was listening to on my computer."}
    proposition["tokens"] = sorted(_tokenize(proposition["text"]))
    audio_row = {
        "text": (
            "Johl came into my room and would turn off or stop what I was listening to on my computer. "
            "I acknowledge this likely occurred on many occasions."
        ),
        "source_row_id": "fact:test-audio-row",
        "comparison_mode": "contested_narrative",
    }
    passive_listening_row = {
        "text": (
            "At one point in September I was having an online appointment with my psychologist, "
            "during which Johl yelled through the closed door contradicting what I was saying in a private appointment "
            "and I did consider that he may have listening to previous sessions."
        ),
        "source_row_id": "fact:test-passive-listening-row",
        "comparison_mode": "contested_narrative",
    }

    audio_score = _score_proposition_against_source_row(proposition, audio_row)
    passive_score = _score_proposition_against_source_row(proposition, passive_listening_row)

    assert audio_score["adjusted_score"] > passive_score["adjusted_score"]


def test_score_proposition_does_not_treat_room_isolation_sentence_as_audio_control_family() -> None:
    proposition = {"text": "Johl came into my room and would turn off or stop what I was listening to on my computer."}
    proposition["tokens"] = sorted(_tokenize(proposition["text"]))
    audio_row = {
        "text": (
            "Johl came into my room and would turn off or stop what I was listening to on my computer. "
            "I acknowledge this likely occurred on many occasions."
        ),
        "source_row_id": "fact:test-audio-row",
        "comparison_mode": "contested_narrative",
    }
    room_isolation_row = {
        "text": "I said I would lock my doors and stay in my room.",
        "source_row_id": "fact:test-room-isolation-row",
        "comparison_mode": "contested_narrative",
    }

    audio_score = _score_proposition_against_source_row(proposition, audio_row)
    room_score = _score_proposition_against_source_row(proposition, room_isolation_row)

    assert audio_score["adjusted_score"] > room_score["adjusted_score"]


def test_score_proposition_does_not_treat_generic_computer_reference_as_audio_control_family() -> None:
    proposition = {"text": "Johl came into my room and would turn off or stop what I was listening to on my computer."}
    proposition["tokens"] = sorted(_tokenize(proposition["text"]))
    audio_row = {
        "text": (
            "Johl came into my room and would turn off or stop what I was listening to on my computer. "
            "I acknowledge this likely occurred on many occasions."
        ),
        "source_row_id": "fact:test-audio-row",
        "comparison_mode": "contested_narrative",
    }
    generic_computer_row = {
        "text": "These files were transcribed locally by a computer program, and then I would search for my name, so I could understand what I was doing wrong.",
        "source_row_id": "fact:test-generic-computer-row",
        "comparison_mode": "contested_narrative",
    }

    audio_score = _score_proposition_against_source_row(proposition, audio_row)
    generic_score = _score_proposition_against_source_row(proposition, generic_computer_row)

    assert audio_score["adjusted_score"] > generic_score["adjusted_score"]


def test_score_proposition_prefers_keyboard_family_row_over_audio_sibling_row() -> None:
    proposition = {"text": "Johl came into my room and pulled out the keyboard so I couldn’t type."}
    proposition["tokens"] = sorted(_tokenize(proposition["text"]))
    keyboard_row = {
        "text": (
            "Johl came into my room and pulled out the keyboard so I couldn't type. "
            "This incident occurred approximately one year prior to the alleged timeframe."
        ),
        "source_row_id": "fact:test-keyboard-row",
        "comparison_mode": "contested_narrative",
    }
    audio_row = {
        "text": (
            "Johl came into my room and would turn off or stop what I was listening to on my computer. "
            "I acknowledge this likely occurred on many occasions."
        ),
        "source_row_id": "fact:test-audio-row",
        "comparison_mode": "contested_narrative",
    }

    keyboard_score = _score_proposition_against_source_row(proposition, keyboard_row)
    audio_score = _score_proposition_against_source_row(proposition, audio_row)

    assert keyboard_score["adjusted_score"] > audio_score["adjusted_score"]


def test_score_proposition_prefers_epoa_revocation_row_over_rta_row() -> None:
    proposition = {"text": "In August 2024, I took steps to revoke my EPOA."}
    proposition["tokens"] = sorted(_tokenize(proposition["text"]))
    revocation_row = {
        "text": (
            "In August 2024 I took steps to revoke my EPOA. "
            "I had only received the revocation three weeks ago. "
            "This is corroborated by the dated signature on the revocation documents."
        ),
        "source_row_id": "fact:test-revocation-row",
        "comparison_mode": "contested_narrative",
    }
    rta_row = {
        "text": (
            "On 7 August 2024, I had filed with the RTA for a Dispute Resolution service, "
            "regarding the issues surrounding John and my tenancy."
        ),
        "source_row_id": "fact:test-rta-row",
        "comparison_mode": "contested_narrative",
    }

    revocation_score = _score_proposition_against_source_row(proposition, revocation_row)
    rta_score = _score_proposition_against_source_row(proposition, rta_row)

    assert revocation_score["adjusted_score"] > rta_score["adjusted_score"]
