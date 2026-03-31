from __future__ import annotations

from src.policy.wikidata_structural_geometry import (
    build_checked_disjointness_cues,
    build_checked_disjointness_rows,
    build_checked_hotspot_cues,
    build_checked_hotspot_rows,
    build_checked_qualifier_drift_cues,
    build_checked_qualifier_drift_row,
    build_dense_disjointness_cues,
    build_dense_disjointness_row,
    build_dense_hotspot_cues,
    build_dense_hotspot_rows,
    build_dense_qualifier_drift_cues,
    build_dense_qualifier_drift_row,
)


def _drift_fixture() -> dict[str, object]:
    return {
        "slot_id": "Q100104196|P166",
        "severity": "medium",
        "from_window": "t1",
        "to_window": "t2",
        "projection_path": "tests/fixtures/wikidata/drift/projection.json",
        "qualifier_signatures_t1": ["a"],
        "qualifier_signatures_t2": ["b", "c"],
        "qualifier_property_set_t1": ["P585"],
        "qualifier_property_set_t2": ["P585", "P580"],
    }


def test_build_checked_qualifier_drift_row_and_cues() -> None:
    row = build_checked_qualifier_drift_row(
        drift=_drift_fixture(),
        recommended_next_action="inspect_qualifier_delta",
    )
    cues = build_checked_qualifier_drift_cues(row)

    assert row["source_kind"] == "qualifier_drift_projection"
    assert row["review_item_id"] == "review:qualifier_drift:Q100104196|P166"
    assert len(cues) == 3
    assert cues[0]["cue_kind"] == "qualifier_signature_delta"
    assert cues[-1]["cue_kind"] == "qualifier_property_set"
    assert cues[-1]["cue_value"] == "P585 -> P585,P580"


def test_build_dense_qualifier_drift_row_and_cues() -> None:
    row = build_dense_qualifier_drift_row(
        drift_row=_drift_fixture(),
        review_item_id="review:qualifier_drift:Q100104196|P166",
        source_path="tests/fixtures/wikidata/drift/projection.json",
        recommended_next_action="inspect_qualifier_delta",
    )
    cues = build_dense_qualifier_drift_cues(row)

    assert row["source_kind"] == "qualifier_drift_summary"
    assert row["source_row_id"] == "source:dense:qualifier_drift:Q100104196|P166"
    assert len(cues) == 2
    assert all(cue["cue_kind"] == "qualifier_signature_delta" for cue in cues)


def test_build_checked_hotspot_rows_and_cues() -> None:
    pack = {
        "pack_id": "software_entity_kind_collapse_pack_v0",
        "hotspot_family": "software_entity_kind_collapse",
        "cluster_count": 4,
        "promotion_status": "held",
        "hold_reason": "awaiting_manifest_promotion",
        "source_artifacts": ["docs/planning/wikidata_hotspot_pilot_pack_v1.manifest.json"],
        "sample_questions": ["Why is GNU grouped with GNU Project?"],
    }
    rows = build_checked_hotspot_rows(
        pack=pack,
        workload_class="governance_gap",
        review_status="review_required",
        recommended_next_action="inspect_hotspot_pack",
    )
    cues = [cue for row in rows for cue in build_checked_hotspot_cues(row)]

    assert rows[0]["source_kind"] == "hotspot_pack_summary"
    assert rows[1]["source_kind"] == "hotspot_sample_question"
    assert any(cue["cue_kind"] == "hold_reason" for cue in cues)
    assert any(cue["cue_kind"] == "source_artifact" for cue in cues)
    assert any(cue["cue_kind"] == "sample_question" for cue in cues)


def test_build_dense_hotspot_rows_and_cues() -> None:
    pack = {
        "pack_id": "software_entity_kind_collapse_pack_v0",
        "hold_reason": "awaiting_manifest_promotion",
        "status": "held",
        "focus_qids": ["Q1", "Q2"],
        "candidate_cluster_families": ["software_entity_kind_collapse"],
        "source_artifacts": ["docs/planning/wikidata_hotspot_pilot_pack_v1.manifest.json"],
    }
    rows = build_dense_hotspot_rows(
        pack=pack,
        item_id="review:hotspot_pack:software_entity_kind_collapse_pack_v0",
        workload_class="governance_gap",
        review_status="review_required",
        recommended_next_action="inspect_hotspot_pack",
        source_path="docs/planning/wikidata_hotspot_pilot_pack_v1.manifest.json",
    )
    cues = [cue for row in rows for cue in build_dense_hotspot_cues(row)]

    assert rows[0]["source_kind"] == "hotspot_pack_summary"
    assert any(row["source_kind"] == "hotspot_focus_qid" for row in rows)
    assert any(row["source_kind"] == "hotspot_cluster_family" for row in rows)
    assert any(cue["cue_kind"] == "focus_qid" for cue in cues)
    assert any(cue["cue_kind"] == "cluster_family" for cue in cues)


def test_build_checked_disjointness_rows_and_cues() -> None:
    case = {
        "case_id": "working_fluid_contradiction",
        "source_path": "tests/fixtures/wikidata/disjointness/working_fluid.json",
        "pair_labels": ["Working fluid vs fluidized bed"],
        "subclass_violation_count": 2,
        "instance_violation_count": 1,
    }
    rows = build_checked_disjointness_rows(
        case=case,
        workload_class="structural_contradiction",
        review_status="review_required",
        recommended_next_action="inspect_disjointness_case",
    )
    cues = [cue for row in rows for cue in build_checked_disjointness_cues(row)]

    assert rows[0]["source_kind"] == "disjointness_pair"
    assert any(cue["cue_kind"] == "pair_label" for cue in cues)
    assert any(cue["cue_kind"] == "violation_counts" for cue in cues)


def test_build_dense_disjointness_row_and_cues() -> None:
    row = build_dense_disjointness_row(
        case_id="working_fluid_contradiction",
        review_item_id="review:disjointness_case:working_fluid_contradiction",
        workload_class="structural_contradiction",
        review_status="review_required",
        recommended_next_action="inspect_disjointness_case",
        source_path="tests/fixtures/wikidata/disjointness/working_fluid.json",
        index=1,
        text="Working fluid (Q1) P31 Fluidized bed (Q2)",
        subject="Q1",
        value="Q2",
        property_pid="P31",
        qualifier_keys=["P585"],
    )
    cues = build_dense_disjointness_cues(row)

    assert row["source_kind"] == "disjointness_statement_bundle"
    assert cues[0]["cue_kind"] == "property_pid"
    assert cues[1]["cue_kind"] == "qualifier_property"
