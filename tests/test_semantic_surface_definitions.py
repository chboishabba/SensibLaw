from __future__ import annotations

from src.models.proposition_identity import PROPOSITION_IDENTITY_SCHEMA_VERSION
from src.models.proposition_relation import PROPOSITION_RELATION_SCHEMA_VERSION
from src.models.review_claim_record import REVIEW_CANDIDATE_SCHEMA_VERSION
from src.policy.affidavit_extraction_hints import extract_extraction_hints as affidavit_extract_extraction_hints
from src.policy.candidate_surface import (
    CANDIDATE_SURFACE_SCHEMA_VERSION,
    build_candidate_surface,
)
from src.policy.claim_surface import (
    CLAIM_IDENTITY_SURFACE_SCHEMA_VERSION,
    CLAIM_RELATION_SURFACE_SCHEMA_VERSION,
    build_claim_identity_surface,
    build_claim_relation_surface,
)
from src.policy.decision_surface import (
    DECISION_SURFACE_SCHEMA_VERSION,
    build_decision_surface,
)
from src.policy.hint_surface import extract_extraction_hints
from src.policy.review_workflow_summary import build_count_priority_workflow_summary
from src.policy.text_surface import (
    TEXT_SURFACE_SCHEMA_VERSION,
    build_text_surface,
    strip_enumeration_prefix,
    tokenize_canonical_text,
)


def test_text_surface_owns_review_text_shape_and_shared_normalizers() -> None:
    surface = build_text_surface(
        text="  Applicant filed complaint  ",
        text_role="claim_display_label",
        source_kind="review_bundle",
        anchor_refs={"fact_id": "fact:1", "empty": ""},
        text_ref={"text_id": "text:1", "unit_id": "unit:1", "ignore": None},
    )

    assert surface == {
        "text": "Applicant filed complaint",
        "text_role": "claim_display_label",
        "source_kind": "review_bundle",
        "anchor_refs": {"fact_id": "fact:1"},
        "text_ref": {"text_id": "text:1", "unit_id": "unit:1"},
    }
    assert strip_enumeration_prefix("1. Applicant filed complaint") == "Applicant filed complaint"
    assert "organization" in tokenize_canonical_text("The organisation responded.")


def test_candidate_and_claim_surfaces_delegate_to_shared_record_models() -> None:
    candidate = build_candidate_surface(
        candidate_id=" fact:1 ",
        candidate_kind=" review_queue_row ",
        source_kind=" review_bundle ",
        selection_basis={"basis_kind": "review_queue_row"},
        anchor_refs={"fact_id": "fact:1"},
    )
    identity = build_claim_identity_surface(
        proposition_id="fact:1",
        family_id="au_fact_review_bundle",
        cohort_id="semantic:1",
        root_artifact_id="run:1",
        lane="au",
        source_family="au_fact_review_bundle",
        basis_kind="review_queue_row",
        local_id="fact:1",
        source_kind="review_bundle",
        upstream_artifact_ids=["run:1", "semantic:1"],
        anchor_refs={"fact_id": "fact:1"},
    )
    relation = build_claim_relation_surface(
        relation_id="rel:1",
        source_proposition_id="fact:1",
        target_proposition_id="prop:2",
        relation_kind="targets",
        source_kind="review_bundle",
        anchor_refs={"fact_id": "fact:1"},
    )

    assert candidate["schema_version"] == CANDIDATE_SURFACE_SCHEMA_VERSION == REVIEW_CANDIDATE_SCHEMA_VERSION
    assert identity["schema_version"] == CLAIM_IDENTITY_SURFACE_SCHEMA_VERSION == PROPOSITION_IDENTITY_SCHEMA_VERSION
    assert relation["schema_version"] == CLAIM_RELATION_SURFACE_SCHEMA_VERSION == PROPOSITION_RELATION_SCHEMA_VERSION


def test_hint_and_decision_surfaces_are_canonical_owners_with_legacy_adapters() -> None:
    text = "On 13 November 2024 [00:01:05 -> 00:02:10] the appeal was dismissed."
    tokenize = lambda value: value.lower().replace("[", " ").replace("]", " ").replace("->", " ").replace(".", " ").split()

    shared_hints = extract_extraction_hints(text, tokenize=tokenize)
    adapter_hints = affidavit_extract_extraction_hints(text, tokenize=tokenize)
    assert shared_hints == adapter_hints

    shared_decision = build_decision_surface(
        counts={"review_queue_count": "2"},
        promotion_gate={"decision": "audit"},
        rules=[
            {
                "count_key": "review_queue_count",
                "threshold": 1,
                "stage": "inspect",
                "title": "Inspect queue",
                "recommended_view": "review_queue",
                "reason_template": "Need review for {review_queue_count} queued items",
            }
        ],
        default_step={
            "stage": "record",
            "title": "Record",
            "recommended_view": "summary",
            "reason_template": "Done",
        },
    )
    adapter_decision = build_count_priority_workflow_summary(
        counts={"review_queue_count": "2"},
        promotion_gate={"decision": "audit"},
        rules=[
            {
                "count_key": "review_queue_count",
                "threshold": 1,
                "stage": "inspect",
                "title": "Inspect queue",
                "recommended_view": "review_queue",
                "reason_template": "Need review for {review_queue_count} queued items",
            }
        ],
        default_step={
            "stage": "record",
            "title": "Record",
            "recommended_view": "summary",
            "reason_template": "Done",
        },
    )

    assert shared_decision["reason"] == "Need review for 2 queued items"
    assert shared_decision == adapter_decision
