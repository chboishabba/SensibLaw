from __future__ import annotations

try:
    from src.policy.wikidata_review_queue import (
        make_bundles,
        make_provisional_rows,
        next_action_for_workload,
    )
except ModuleNotFoundError:
    from policy.wikidata_review_queue import (
        make_bundles,
        make_provisional_rows,
        next_action_for_workload,
    )


def test_next_action_for_workload_preserves_structural_review_mapping() -> None:
    assert next_action_for_workload("baseline_confirmation") == "retain as checked baseline"
    assert next_action_for_workload("governance_gap") == "promote held hotspot pack through manifest governance"
    assert next_action_for_workload("structural_contradiction") == "review contradiction culprits and preserve disjointness evidence"


def test_make_provisional_rows_and_bundles_rank_by_workload_and_cue_priority() -> None:
    review_items = [
        {
            "review_item_id": "review:contradiction",
            "recommended_next_action": next_action_for_workload("structural_contradiction"),
        },
        {
            "review_item_id": "review:baseline",
            "recommended_next_action": next_action_for_workload("baseline_confirmation"),
        },
    ]
    source_rows = [
        {
            "source_row_id": "source:1",
            "review_item_id": "review:contradiction",
            "workload_class": "structural_contradiction",
            "text": "Contradiction row",
        },
        {
            "source_row_id": "source:2",
            "review_item_id": "review:baseline",
            "workload_class": "baseline_confirmation",
            "text": "Baseline row",
        },
    ]
    candidate_cues = [
        {
            "cue_id": "source:1:pair",
            "review_item_id": "review:contradiction",
            "source_row_id": "source:1",
            "cue_kind": "pair_label",
            "cue_value": "pair-a",
        },
        {
            "cue_id": "source:2:artifact",
            "review_item_id": "review:baseline",
            "source_row_id": "source:2",
            "cue_kind": "source_artifact",
            "cue_value": "artifact-a",
        },
    ]

    provisional_rows = make_provisional_rows(review_items, source_rows, candidate_cues)
    bundles = make_bundles(provisional_rows, source_rows)

    assert provisional_rows[0]["review_item_id"] == "review:contradiction"
    assert provisional_rows[0]["priority_rank"] == 1
    assert bundles[0]["review_item_id"] == "review:contradiction"
    assert bundles[0]["bundle_rank"] == 1
