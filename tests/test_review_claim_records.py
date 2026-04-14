from __future__ import annotations

from src.models.proposition_relation import (
    PROPOSITION_RELATION_SCHEMA_VERSION,
    build_proposition_relation_dict,
)
from src.models.review_claim_record import build_review_claim_record_dict
from src.policy.review_targeting_contract import (
    GWBTargetingCandidate,
    assess_gwb_semantic_separability,
    build_gwb_ambiguous_seed_inventory,
    build_gwb_targeting_result,
    normalize_gwb_target_split_kind,
    summarize_gwb_targeting_results,
)
from src.policy.review_claim_records import (
    attach_review_item_relations_by_seed_id,
    build_affidavit_target_proposition_identity,
    build_gwb_targeting_results_from_review_claim_records,
    build_review_queue_target_proposition_identity,
    build_review_queue_proposition_relation,
    build_review_claim_records_from_affidavit_rows,
    build_review_claim_records_from_queue_rows,
    build_review_claim_records_from_review_rows,
)


def test_build_review_claim_records_from_queue_rows_preserves_au_review_fields() -> None:
    records = build_review_claim_records_from_queue_rows(
        rows=[
            {
                "fact_id": "fact:1",
                "label": "Applicant filed complaint",
                "event_ids": ["ev1"],
                "source_ids": ["src1"],
                "statement_ids": ["stmt1"],
                "reason_codes": ["needs_review"],
                "policy_outcomes": ["must_review"],
                "candidate_status": "candidate_conflict",
                "latest_review_status": "open",
            }
        ],
        lane="au",
        family_id="au_fact_review_bundle",
        cohort_id="semantic:1",
        root_artifact_id="factrun:1",
        source_family="au_fact_review_bundle",
        recommended_view="authority_follow",
        queue_family="authority_follow",
    )

    assert len(records) == 1
    record = records[0]
    assert record["claim_id"] == "fact:1"
    assert record["state"] == "review_claim"
    assert record["state_basis"] == "review_bundle"
    assert record["proposition_identity"]["proposition_id"] == "fact:1"
    assert record["proposition_identity"]["identity_basis"]["basis_kind"] == "review_queue_row"
    assert record["proposition_identity"]["provenance"]["anchor_refs"]["event_ids"] == ["ev1"]
    assert record["review_candidate"]["candidate_id"] == "fact:1"
    assert record["review_candidate"]["candidate_kind"] == "review_queue_row"
    assert record["review_candidate"]["source_kind"] == "review_bundle"
    assert record["review_candidate"]["selection_basis"]["candidate_status"] == "candidate_conflict"
    assert record["review_candidate"]["anchor_refs"]["fact_id"] == "fact:1"
    assert record["review_text"]["text"] == "Applicant filed complaint"
    assert record["review_text"]["text_role"] == "claim_display_label"
    assert record["review_text"]["source_kind"] == "review_bundle"
    assert record["review_text"]["anchor_refs"]["fact_id"] == "fact:1"
    assert "target_proposition_identity" not in record
    assert "proposition_relation" not in record
    assert record["provenance"]["event_ids"] == ["ev1"]
    assert record["decision_basis"]["reason_codes"] == ["needs_review"]
    assert record["review_route"]["recommended_view"] == "authority_follow"


def test_build_review_claim_records_from_review_rows_preserves_gwb_review_fields() -> None:
    records = build_review_claim_records_from_review_rows(
        rows=[
            {
                "source_row_id": "row:1",
                "source_kind": "gwb_seed_event",
                "source_family": "gwb_public_review",
                "text": "Section 1 imposes a filing requirement.",
                "seed_id": "seed:1",
                "review_status": "missing_review",
                "primary_workload_class": "linkage_gap",
                "workload_classes": ["linkage_gap"],
                "support_kinds": ["authority"],
                "linkage_kind": "legal_interaction",
                "text_id": "sample:text:1",
                "segment_id": "sample:segment:1",
                "unit_id": "sample:segment:1:unit:0",
                "envelope_id": "sample:text:1:envelope:1",
            }
        ],
        lane="gwb",
        family_id="gwb_public_review",
        cohort_id="gwb_public_review_v1",
        root_artifact_id="gwb_public_review_v1",
        source_family="gwb_public_review",
        recommended_view="source_review_rows",
    )

    assert len(records) == 1
    record = records[0]
    assert record["claim_id"] == "row:1"
    assert record["state_basis"] == "source_review_row"
    assert record["proposition_identity"]["proposition_id"] == "row:1"
    assert record["proposition_identity"]["identity_basis"]["basis_kind"] == "source_review_row"
    assert record["proposition_identity"]["provenance"]["anchor_refs"]["seed_id"] == "seed:1"
    assert record["review_candidate"]["candidate_id"] == "row:1"
    assert record["review_candidate"]["candidate_kind"] == "review_source_row"
    assert record["review_candidate"]["selection_basis"]["review_status"] == "missing_review"
    assert record["review_candidate"]["anchor_refs"]["seed_id"] == "seed:1"
    assert record["review_text"]["text"] == "Section 1 imposes a filing requirement."
    assert record["review_text"]["text_role"] == "review_source_text"
    assert record["review_text"]["anchor_refs"]["source_row_id"] == "row:1"
    assert record["review_text"]["text_ref"] == {
        "text_id": "sample:text:1",
        "segment_id": "sample:segment:1",
        "unit_id": "sample:segment:1:unit:0",
        "envelope_id": "sample:text:1:envelope:1",
    }
    assert "proposition_relation" not in record
    assert record["provenance"]["seed_id"] == "seed:1"
    assert record["decision_basis"]["linkage_kind"] == "legal_interaction"
    assert record["review_route"]["actionability"] == "must_review"


def test_build_review_claim_records_from_queue_rows_preserves_explicit_text_ref() -> None:
    records = build_review_claim_records_from_queue_rows(
        rows=[
            {
                "fact_id": "fact:2",
                "label": "Applicant filed complaint",
                "event_ids": ["ev2"],
                "source_ids": ["src2"],
                "statement_ids": ["stmt2"],
                "text_ref": {
                    "text_id": "queue:text:2",
                    "segment_id": "queue:segment:2",
                    "envelope_id": "queue:text:2:envelope:1",
                },
            }
        ],
        lane="au",
        family_id="au_fact_review_bundle",
        cohort_id="semantic:2",
        root_artifact_id="factrun:2",
        source_family="au_fact_review_bundle",
        recommended_view="authority_follow",
        queue_family="authority_follow",
    )

    assert records[0]["review_text"]["text_ref"] == {
        "text_id": "queue:text:2",
        "segment_id": "queue:segment:2",
        "envelope_id": "queue:text:2:envelope:1",
    }


def test_build_gwb_targeting_result_preserves_singleton_selection() -> None:
    result = build_gwb_targeting_result(
        claim_id="row:1",
        seed_id="seed:1",
        candidate_targets=[
            GWBTargetingCandidate(
                seed_id="seed:1",
                review_item_id="review:1",
                candidate_ref="review:1",
                candidate_kind="review_item_target",
                relation_kind="addresses",
                selection_basis="seed_linkage",
                target_proposition_identity={"proposition_id": "gwb_review_item_prop:gwb_public_review_v1:seed:1"},
                anchor_refs={"seed_id": "seed:1", "review_item_id": "review:1"},
            )
        ],
    )

    assert result.selection_mode == "singleton_seed_linkage"
    assert result.candidate_count == 1
    assert result.selected_target is not None
    assert result.selected_target.review_item_id == "review:1"

    assessment = assess_gwb_semantic_separability(result=result)

    assert assessment["assessment_status"] == "not_applicable"
    assert assessment["reason_codes"] == ["singleton_target"]


def test_attach_review_item_relations_by_seed_id_holds_multi_candidate_seed() -> None:
    records = build_review_claim_records_from_review_rows(
        rows=[
            {
                "source_row_id": "row:1",
                "source_kind": "gwb_seed_event",
                "source_family": "gwb_public_review",
                "text": "Section 1 imposes a filing requirement.",
                "seed_id": "seed:1",
                "review_status": "missing_review",
                "primary_workload_class": "linkage_gap",
                "workload_classes": ["linkage_gap"],
                "support_kinds": ["authority"],
                "linkage_kind": "legal_interaction",
            }
        ],
        lane="gwb",
        family_id="gwb_public_review",
        cohort_id="gwb_public_review_v1",
        root_artifact_id="gwb_public_review_v1",
        source_family="gwb_public_review",
        recommended_view="source_review_rows",
    )

    attached = attach_review_item_relations_by_seed_id(
        review_claim_records=records,
        review_item_rows=[
            {"seed_id": "seed:1", "review_item_id": "review:1"},
            {"seed_id": "seed:1", "review_item_id": "review:2"},
        ],
    )

    assert len(attached) == 1
    record = attached[0]
    assert "target_proposition_identity" not in record
    assert "proposition_relation" not in record
    assert "target_proposition_id" not in record["review_candidate"]
    assert record["review_candidate"]["selection_basis"]["targeting_mode"] == "multi_candidate_unresolved"
    assert record["review_candidate"]["selection_basis"]["candidate_count"] == 2


def test_build_gwb_targeting_results_from_review_claim_records_reports_multi_candidate_seed() -> None:
    records = build_review_claim_records_from_review_rows(
        rows=[
            {
                "source_row_id": "row:1",
                "source_kind": "gwb_seed_event",
                "source_family": "gwb_public_review",
                "text": "Section 1 imposes a filing requirement.",
                "seed_id": "seed:1",
                "review_status": "missing_review",
                "primary_workload_class": "linkage_gap",
                "workload_classes": ["linkage_gap"],
                "support_kinds": ["authority"],
                "linkage_kind": "legal_interaction",
            }
        ],
        lane="gwb",
        family_id="gwb_public_review",
        cohort_id="gwb_public_review_v1",
        root_artifact_id="gwb_public_review_v1",
        source_family="gwb_public_review",
        recommended_view="source_review_rows",
    )

    targeting_results = build_gwb_targeting_results_from_review_claim_records(
        review_claim_records=records,
        review_item_rows=[
            {"seed_id": "seed:1", "review_item_id": "review:1"},
            {"seed_id": "seed:1", "review_item_id": "review:2"},
        ],
    )

    assert len(targeting_results) == 1
    assert targeting_results[0].selection_mode == "multi_candidate_unresolved"
    assert targeting_results[0].candidate_count == 2
    assert targeting_results[0].candidate_targets[0].target_split_kind is None

    assessment = assess_gwb_semantic_separability(result=targeting_results[0])

    assert assessment["assessment_status"] == "insufficient_semantics"
    assert assessment["reason_codes"] == ["missing_target_split_semantics"]


def test_gwb_semantic_separability_is_separable_when_split_semantics_are_distinct() -> None:
    result = build_gwb_targeting_result(
        claim_id="row:1",
        seed_id="seed:multi",
        candidate_targets=[
            GWBTargetingCandidate(
                seed_id="seed:multi",
                review_item_id="review:event:1",
                candidate_ref="review:event:1",
                candidate_kind="review_item_target",
                relation_kind="addresses",
                selection_basis="seed_linkage",
                target_proposition_identity={"proposition_id": "prop:event:1"},
                anchor_refs={"seed_id": "seed:multi", "review_item_id": "review:event:1"},
                target_split_kind="matched_event",
                target_split_value="event:1",
                target_text_or_label="event:1",
                target_coverage_basis="matched_event",
            ),
            GWBTargetingCandidate(
                seed_id="seed:multi",
                review_item_id="review:event:2",
                candidate_ref="review:event:2",
                candidate_kind="review_item_target",
                relation_kind="addresses",
                selection_basis="seed_linkage",
                target_proposition_identity={"proposition_id": "prop:event:2"},
                anchor_refs={"seed_id": "seed:multi", "review_item_id": "review:event:2"},
                target_split_kind="matched_event",
                target_split_value="event:2",
                target_text_or_label="event:2",
                target_coverage_basis="matched_event",
            ),
        ],
    )

    assessment = assess_gwb_semantic_separability(result=result)

    assert assessment["assessment_status"] == "separable"
    assert assessment["reason_codes"] == ["distinct_target_splits"]


def test_summarize_gwb_targeting_results_reports_ambiguity_inventory() -> None:
    singleton = build_gwb_targeting_result(
        claim_id="row:1",
        seed_id="seed:1",
        candidate_targets=[
            GWBTargetingCandidate(
                seed_id="seed:1",
                review_item_id="review:1",
                candidate_ref="review:1",
                candidate_kind="review_item_target",
                relation_kind="addresses",
                selection_basis="seed_linkage",
                target_proposition_identity={"proposition_id": "prop:1"},
                anchor_refs={"seed_id": "seed:1"},
            )
        ],
    )
    ambiguous = build_gwb_targeting_result(
        claim_id="row:2",
        seed_id="seed:2",
        candidate_targets=[
            GWBTargetingCandidate(
                seed_id="seed:2",
                review_item_id="review:2",
                candidate_ref="review:2",
                candidate_kind="review_item_target",
                relation_kind="addresses",
                selection_basis="seed_linkage",
                target_proposition_identity={"proposition_id": "prop:2"},
                anchor_refs={"seed_id": "seed:2"},
            ),
            GWBTargetingCandidate(
                seed_id="seed:2",
                review_item_id="review:3",
                candidate_ref="review:3",
                candidate_kind="review_item_target",
                relation_kind="addresses",
                selection_basis="seed_linkage",
                target_proposition_identity={"proposition_id": "prop:3"},
                anchor_refs={"seed_id": "seed:2"},
            ),
        ],
    )

    summary = summarize_gwb_targeting_results([singleton, ambiguous])

    assert summary["selection_mode_counts"]["singleton_seed_linkage"] == 1
    assert summary["selection_mode_counts"]["multi_candidate_unresolved"] == 1
    assert summary["selection_basis_counts"]["seed_linkage"] == 2
    assert summary["top_ambiguous_seeds"][0]["seed_id"] == "seed:2"
    assert summary["top_ambiguous_seeds"][0]["candidate_count"] == 2


def test_build_gwb_ambiguous_seed_inventory_reports_sorted_operator_view() -> None:
    ambiguous = build_gwb_targeting_result(
        claim_id="row:2",
        seed_id="seed:2",
        candidate_targets=[
            GWBTargetingCandidate(
                seed_id="seed:2",
                review_item_id="review:event:1",
                candidate_ref="review:event:1",
                candidate_kind="review_item_target",
                relation_kind="addresses",
                selection_basis="seed_linkage",
                target_proposition_identity={"proposition_id": "prop:event:1"},
                anchor_refs={"seed_id": "seed:2", "review_item_id": "review:event:1"},
                target_split_kind="matched_event",
                target_split_value="event:1",
                target_text_or_label="event 1",
                target_coverage_basis="matched_event",
            ),
            GWBTargetingCandidate(
                seed_id="seed:2",
                review_item_id="review:event:2",
                candidate_ref="review:event:2",
                candidate_kind="review_item_target",
                relation_kind="addresses",
                selection_basis="seed_linkage",
                target_proposition_identity={"proposition_id": "prop:event:2"},
                anchor_refs={"seed_id": "seed:2", "review_item_id": "review:event:2"},
                target_split_kind="matched_event",
                target_split_value="event:2",
                target_text_or_label="event 2",
                target_coverage_basis="matched_event",
            ),
        ],
    )

    inventory = build_gwb_ambiguous_seed_inventory([ambiguous])

    assert len(inventory) == 1
    assert inventory[0]["seed_id"] == "seed:2"
    assert inventory[0]["candidate_count"] == 2
    assert inventory[0]["selection_mode"] == "multi_candidate_unresolved"
    assert inventory[0]["candidate_kinds"] == ["review_item_target"]
    assert inventory[0]["relation_kinds"] == ["addresses"]
    assert inventory[0]["anchor_ref_keys"] == ["review_item_id", "seed_id"]
    assert inventory[0]["normalized_split_kinds"] == ["event_split"]
    assert inventory[0]["semantic_separability"] == "separable"
    assert inventory[0]["semantic_reason_codes"] == ["distinct_target_splits"]
    assert inventory[0]["candidate_cards"] == [
        {
            "candidate_ref": "review:event:1",
            "candidate_kind": "review_item_target",
            "normalized_split_kind": "event_split",
            "split_value": "event:1",
            "text_or_label": "event 1",
            "coverage_basis": "matched_event",
            "target_proposition_id": "prop:event:1",
        },
        {
            "candidate_ref": "review:event:2",
            "candidate_kind": "review_item_target",
            "normalized_split_kind": "event_split",
            "split_value": "event:2",
            "text_or_label": "event 2",
            "coverage_basis": "matched_event",
            "target_proposition_id": "prop:event:2",
        },
    ]


def test_normalize_gwb_target_split_kind_uses_bounded_vocab() -> None:
    assert normalize_gwb_target_split_kind("matched_event") == "event_split"
    assert normalize_gwb_target_split_kind("matched_source_family") == "family_split"
    assert normalize_gwb_target_split_kind("other") == "no_split"


def test_build_review_claim_record_dict_preserves_explicit_proposition_relation() -> None:
    relation = build_proposition_relation_dict(
        relation_id="rel:1",
        source_proposition_id="fact:1",
        target_proposition_id="seed:1",
        relation_kind="addresses",
        evidence_status="review_only",
        source_kind="review_bundle",
        upstream_artifact_ids=["factrun:1", "semantic:1"],
        anchor_refs={"fact_id": "fact:1", "seed_id": "seed:1"},
    )

    record = build_review_claim_record_dict(
        claim_id="fact:1",
        candidate_id="fact:1",
        family_id="au_fact_review_bundle",
        cohort_id="semantic:1",
        root_artifact_id="factrun:1",
        lane="au",
        source_family="au_fact_review_bundle",
        state="review_claim",
        state_basis="review_bundle",
        evidence_status="review_only",
        review_candidate={
            "schema_version": "sl.review_candidate.v0_1",
            "candidate_id": "fact:1",
            "candidate_kind": "review_queue_row",
            "source_kind": "review_bundle",
            "selection_basis": {"basis_kind": "review_queue_row"},
        },
        proposition_relation=relation,
        review_text={"text": "Applicant filed complaint", "text_role": "claim_display_label"},
        provenance={"source_kind": "review_bundle"},
        decision_basis={"basis_kind": "review_queue_row"},
        review_route={"actionability": "must_review"},
    )

    assert record["proposition_relation"]["schema_version"] == PROPOSITION_RELATION_SCHEMA_VERSION
    assert record["proposition_relation"]["relation_id"] == "rel:1"
    assert record["proposition_relation"]["relation_kind"] == "addresses"
    assert record["proposition_relation"]["target_proposition_id"] == "seed:1"
    assert record["review_candidate"]["candidate_kind"] == "review_queue_row"
    assert record["review_text"]["text"] == "Applicant filed complaint"


def test_build_review_queue_target_proposition_identity_requires_single_event_id() -> None:
    assert (
        build_review_queue_target_proposition_identity(
            row={"event_ids": ["ev1", "ev2"]},
            lane="au",
            family_id="au_fact_review_bundle",
            cohort_id="semantic:1",
            root_artifact_id="factrun:1",
            source_family="au_fact_review_bundle",
        )
        is None
    )


def test_build_review_claim_records_from_queue_rows_can_emit_target_proposition_identity() -> None:
    records = build_review_claim_records_from_queue_rows(
        rows=[
            {
                "fact_id": "fact:1",
                "label": "Applicant filed complaint",
                "event_ids": ["ev1"],
                "source_ids": ["src1"],
                "statement_ids": ["stmt1"],
                "reason_codes": ["needs_review"],
                "policy_outcomes": ["must_review"],
                "candidate_status": "candidate_conflict",
                "latest_review_status": "open",
            }
        ],
        lane="au",
        family_id="au_fact_review_bundle",
        cohort_id="semantic:1",
        root_artifact_id="factrun:1",
        source_family="au_fact_review_bundle",
        recommended_view="authority_follow",
        queue_family="authority_follow",
        include_target_proposition_identity=True,
    )

    assert len(records) == 1
    target_identity = records[0]["target_proposition_identity"]
    assert target_identity["proposition_id"] == "au_event_prop:semantic:1:ev1"
    assert target_identity["identity_basis"]["basis_kind"] == "event_id"
    assert target_identity["identity_basis"]["local_id"] == "ev1"
    assert target_identity["provenance"]["source_kind"] == "review_bundle_target"
    assert target_identity["provenance"]["anchor_refs"]["event_id"] == "ev1"
    assert target_identity["provenance"]["anchor_refs"]["statement_ids"] == ["stmt1"]
    assert records[0]["review_candidate"]["target_proposition_id"] == target_identity["proposition_id"]


def test_build_review_queue_proposition_relation_requires_single_event_id() -> None:
    assert (
        build_review_queue_proposition_relation(
            row={"event_ids": ["ev1", "ev2"]},
            claim_id="fact:1",
            lane="au",
            family_id="au_fact_review_bundle",
            cohort_id="semantic:1",
            root_artifact_id="factrun:1",
            source_family="au_fact_review_bundle",
        )
        is None
    )


def test_build_review_claim_records_from_queue_rows_can_emit_proposition_relation() -> None:
    records = build_review_claim_records_from_queue_rows(
        rows=[
            {
                "fact_id": "fact:1",
                "label": "Applicant filed complaint",
                "event_ids": ["ev1"],
                "source_ids": ["src1"],
                "statement_ids": ["stmt1"],
                "reason_codes": ["needs_review"],
                "policy_outcomes": ["must_review"],
                "candidate_status": "candidate_conflict",
                "latest_review_status": "open",
            },
            {
                "fact_id": "fact:2",
                "label": "Applicant sent follow-up",
                "event_ids": ["ev2", "ev3"],
                "source_ids": ["src2"],
                "statement_ids": ["stmt2"],
                "reason_codes": ["needs_review"],
                "policy_outcomes": ["must_review"],
                "candidate_status": "candidate_conflict",
                "latest_review_status": "open",
            },
        ],
        lane="au",
        family_id="au_fact_review_bundle",
        cohort_id="semantic:1",
        root_artifact_id="factrun:1",
        source_family="au_fact_review_bundle",
        recommended_view="authority_follow",
        queue_family="authority_follow",
        include_target_proposition_identity=True,
        include_proposition_relation=True,
    )

    relation = records[0]["proposition_relation"]
    assert relation["schema_version"] == PROPOSITION_RELATION_SCHEMA_VERSION
    assert relation["relation_kind"] == "addresses"
    assert relation["source_proposition_id"] == "fact:1"
    assert relation["target_proposition_id"] == "au_event_prop:semantic:1:ev1"
    assert relation["evidence_status"] == "review_only"
    assert relation["provenance"]["source_kind"] == "review_bundle"
    assert relation["provenance"]["anchor_refs"]["fact_id"] == "fact:1"
    assert relation["provenance"]["anchor_refs"]["event_id"] == "ev1"
    assert records[0]["review_candidate"]["target_proposition_id"] == "au_event_prop:semantic:1:ev1"
    assert records[0]["review_text"]["text"] == "Applicant filed complaint"
    assert "proposition_relation" not in records[1]


def test_attach_review_item_relations_by_seed_id_adds_target_identity_and_relation() -> None:
    records = build_review_claim_records_from_review_rows(
        rows=[
            {
                "source_row_id": "row:1",
                "source_kind": "gwb_seed_event",
                "source_family": "gwb_public_review",
                "seed_id": "seed:1",
                "review_status": "missing_review",
                "primary_workload_class": "linkage_gap",
                "workload_classes": ["linkage_gap"],
                "support_kinds": ["authority"],
                "linkage_kind": "legal_interaction",
            },
            {
                "source_row_id": "row:2",
                "source_kind": "unresolved_surface",
                "source_family": "gwb_public_review",
                "seed_id": "",
                "review_status": "missing_review",
                "primary_workload_class": "surface_resolution_gap",
                "workload_classes": ["surface_resolution_gap"],
                "support_kinds": [],
                "linkage_kind": "",
            },
        ],
        lane="gwb",
        family_id="gwb_public_review",
        cohort_id="gwb_public_review_v1",
        root_artifact_id="gwb_public_review_v1",
        source_family="gwb_public_review",
        recommended_view="source_review_rows",
    )

    enriched = attach_review_item_relations_by_seed_id(
        review_claim_records=records,
        review_item_rows=[
            {
                "review_item_id": "seed:seed:1",
                "seed_id": "seed:1",
                "coverage_status": "partial",
            }
        ],
    )

    assert enriched[0]["target_proposition_identity"]["identity_basis"]["basis_kind"] == "seed_id"
    assert enriched[0]["target_proposition_identity"]["provenance"]["source_kind"] == "review_item_target"
    assert enriched[0]["target_proposition_identity"]["provenance"]["anchor_refs"]["seed_id"] == "seed:1"
    assert enriched[0]["review_candidate"]["target_proposition_id"] == enriched[0]["target_proposition_identity"]["proposition_id"]
    assert enriched[0]["proposition_relation"]["relation_kind"] == "addresses"
    assert enriched[0]["proposition_relation"]["target_proposition_id"] == enriched[0]["target_proposition_identity"]["proposition_id"]
    assert enriched[0]["proposition_relation"]["provenance"]["anchor_refs"]["review_item_id"] == "seed:seed:1"
    assert "target_proposition_identity" not in enriched[1]
    assert "proposition_relation" not in enriched[1]


def test_build_affidavit_target_proposition_identity_requires_best_source_row_id() -> None:
    assert (
        build_affidavit_target_proposition_identity(
            row={"proposition_id": "aff-prop:p1-s1"},
            lane="affidavit",
            family_id="affidavit_coverage_review",
            cohort_id="affidavit_coverage_review_v1",
            root_artifact_id="affidavit_coverage_review_v1",
            source_family="affidavit_coverage_review",
        )
        is None
    )


def test_build_review_claim_records_from_affidavit_rows_can_emit_weak_relation_subset() -> None:
    records = build_review_claim_records_from_affidavit_rows(
        rows=[
            {
                "proposition_id": "aff-prop:p1-s1",
                "text": "The applicant filed a complaint on 1 March 2024.",
                "paragraph_id": "p1",
                "paragraph_order": 1,
                "sentence_order": 1,
                "coverage_status": "covered",
                "best_source_row_id": "fact:f1",
                "best_match_basis": "segment",
                "best_response_role": "dispute",
            },
            {
                "proposition_id": "aff-prop:p1-s2",
                "text": "The respondent denied the allegation in correspondence.",
                "paragraph_id": "p1",
                "paragraph_order": 1,
                "sentence_order": 2,
                "coverage_status": "unsupported_affidavit",
                "best_source_row_id": "",
                "best_match_basis": "",
                "best_response_role": "",
            },
        ],
        lane="affidavit",
        family_id="affidavit_coverage_review",
        cohort_id="affidavit_coverage_review_v1",
        root_artifact_id="affidavit_coverage_review_v1",
        source_family="affidavit_coverage_review",
        recommended_view="affidavit_rows",
        queue_family="affidavit_rows",
        include_target_proposition_identity=True,
        include_proposition_relation=True,
    )

    assert len(records) == 2
    first = records[0]
    assert first["proposition_identity"]["proposition_id"] == "aff-prop:p1-s1"
    assert first["proposition_identity"]["identity_basis"]["basis_kind"] == "affidavit_proposition_row"
    assert first["target_proposition_identity"]["proposition_id"] == (
        "affidavit_source_row_prop:affidavit_coverage_review_v1:fact:f1"
    )
    assert first["target_proposition_identity"]["identity_basis"]["basis_kind"] == "best_source_row_id"
    assert first["review_candidate"]["candidate_kind"] == "affidavit_proposition_row"
    assert first["review_candidate"]["selection_basis"]["coverage_status"] == "covered"
    assert first["review_candidate"]["anchor_refs"]["paragraph_id"] == "p1"
    assert first["review_candidate"]["target_proposition_id"] == (
        "affidavit_source_row_prop:affidavit_coverage_review_v1:fact:f1"
    )
    assert first["proposition_relation"]["relation_kind"] == "addresses"
    assert first["proposition_relation"]["target_proposition_id"] == (
        "affidavit_source_row_prop:affidavit_coverage_review_v1:fact:f1"
    )
    assert first["proposition_relation"]["provenance"]["anchor_refs"]["best_source_row_id"] == "fact:f1"
    assert first["review_text"]["text"] == "The applicant filed a complaint on 1 March 2024."
    assert first["review_text"]["text_role"] == "claim_text"

    second = records[1]
    assert "target_proposition_identity" not in second
    assert "proposition_relation" not in second
