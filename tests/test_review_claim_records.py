from __future__ import annotations

from src.models.proposition_relation import (
    PROPOSITION_RELATION_SCHEMA_VERSION,
    build_proposition_relation_dict,
)
from src.models.review_claim_record import build_review_claim_record_dict
from src.policy.review_claim_records import (
    attach_review_item_relations_by_seed_id,
    build_affidavit_target_proposition_identity,
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

    assert len(records) == 1
    record = records[0]
    assert record["claim_id"] == "row:1"
    assert record["state_basis"] == "source_review_row"
    assert record["proposition_identity"]["proposition_id"] == "row:1"
    assert record["proposition_identity"]["identity_basis"]["basis_kind"] == "source_review_row"
    assert record["proposition_identity"]["provenance"]["anchor_refs"]["seed_id"] == "seed:1"
    assert "proposition_relation" not in record
    assert record["provenance"]["seed_id"] == "seed:1"
    assert record["decision_basis"]["linkage_kind"] == "legal_interaction"
    assert record["review_route"]["actionability"] == "must_review"


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
        proposition_relation=relation,
        provenance={"source_kind": "review_bundle"},
        decision_basis={"basis_kind": "review_queue_row"},
        review_route={"actionability": "must_review"},
    )

    assert record["proposition_relation"]["schema_version"] == PROPOSITION_RELATION_SCHEMA_VERSION
    assert record["proposition_relation"]["relation_id"] == "rel:1"
    assert record["proposition_relation"]["relation_kind"] == "addresses"
    assert record["proposition_relation"]["target_proposition_id"] == "seed:1"


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
    assert first["proposition_relation"]["relation_kind"] == "addresses"
    assert first["proposition_relation"]["target_proposition_id"] == (
        "affidavit_source_row_prop:affidavit_coverage_review_v1:fact:f1"
    )
    assert first["proposition_relation"]["provenance"]["anchor_refs"]["best_source_row_id"] == "fact:f1"

    second = records[1]
    assert "target_proposition_identity" not in second
    assert "proposition_relation" not in second
