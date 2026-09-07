from __future__ import annotations

import json
from pathlib import Path

from src.ontology.wikidata_nat_batch_prerequisite_runner import (
    BATCH_RESULT_SCHEMA_VERSION,
    build_batch_dry_run,
    build_row_descriptor,
    derive_prerequisite_status,
    routing_family,
    work_signature,
)


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "wikidata"
MANIFEST_PATH = FIXTURE_ROOT / "wikidata_nat_lane_review_manifests_20260401.json"
PACK_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "ontology"
    / "wikidata_migration_packs"
    / "p5991_p14143_climate_pilot_20260328"
    / "migration_pack.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate(
    *,
    classification: str = "split_required",
    receipts: dict | None = None,
) -> dict:
    return {
        "candidate_id": "Q10403939|P5991|1",
        "entity_qid": "Q10403939",
        "classification": classification,
        "action": "split" if classification == "split_required" else "migrate_with_refs",
        "claim_bundle_before": {
            "subject": "Q10403939",
            "statement_id": "Q10403939$ABC",
            "property": "P5991",
            "qualifiers": {
                "P3831": ["Q124883250"],
                "P459": ["Q56296245"],
                "P580": ["+2023-01-01T00:00:00Z"],
                "P582": ["+2023-12-31T00:00:00Z"],
            },
            "references": [{"P854": ["https://example.test/report.pdf"]}],
            "rank": "normal",
        },
        "claim_bundle_after": {
            "subject": "Q10403939",
            "statement_id": "Q10403939$ABC",
            "property": "P14143",
            "qualifiers": {
                "P3831": ["Q124883250"],
                "P459": ["Q56296245"],
                "P580": ["+2023-01-01T00:00:00Z"],
                "P582": ["+2023-12-31T00:00:00Z"],
            },
            "references": [{"P854": ["https://example.test/report.pdf"]}],
            "rank": "normal",
        },
        "prerequisite_receipts": receipts or {},
    }


def test_status_derives_same_carrier_but_does_not_invent_source_payment() -> None:
    status = derive_prerequisite_status(_candidate())
    assert status.same_carrier is True
    assert status.source_support is False
    assert status.first_missing() == "source_support"


def test_explicit_receipts_advance_first_missing_cut() -> None:
    status = derive_prerequisite_status(
        _candidate(receipts={"source_support": {"paid": True}})
    )
    assert status.same_carrier is True
    assert status.source_support is True
    assert status.first_missing() == "qualifier_transport"


def test_safe_classification_does_not_pay_prerequisites() -> None:
    candidate = _candidate(classification="safe_with_reference_transfer")
    status = derive_prerequisite_status(candidate)
    assert routing_family(candidate) == "full_auto"
    assert status.source_support is False
    assert status.semantic_correspondence is False


def test_signature_is_derived_from_current_first_missing() -> None:
    row = build_row_descriptor(
        _candidate(),
        source_cohort="business_family_reconciled",
        source_revision_reference="revision:test",
    )
    signature = work_signature(row)
    assert signature["first_missing_prerequisite"] == "source_support"
    assert signature["required_producer"] == "acquire_source_support"
    assert signature["mechanism"] == "look"
    assert signature["selector_class"] == "zelph_hf_selector"
    assert signature["qualifier_properties"] == ["P3831", "P459", "P580", "P582"]
    assert signature["reference_properties"] == ["P854"]


def test_batch_groups_equal_work_without_collapsing_rows() -> None:
    left = _candidate()
    right = _candidate()
    right["candidate_id"] = "Q10403939|P5991|2"
    right["claim_bundle_before"] = dict(right["claim_bundle_before"])
    right["claim_bundle_after"] = dict(right["claim_bundle_after"])
    right["claim_bundle_before"]["statement_id"] = "Q10403939$DEF"
    right["claim_bundle_after"]["statement_id"] = "Q10403939$DEF"
    manifest = {
        "lane_id": "wikidata_nat_wdu_p5991_p14143",
        "cohorts": [
            {
                "cohort_id": "business_family_reconciled",
                "population": 37665,
            }
        ],
    }
    batch = build_batch_dry_run(
        cohort_manifest=manifest,
        migration_packs=[{"candidates": [left, right]}],
        source_revision_reference="revision:test",
    )
    assert batch["row_count"] == 2
    assert batch["work_group_count"] == 1
    assert batch["work_groups"][0]["member_count"] == 2
    assert len(batch["work_groups"][0]["member_row_refs"]) == 2
    assert batch["work_groups"][0]["member_row_refs"][0] != batch["work_groups"][0]["member_row_refs"][1]


def test_real_nat_artifacts_preserve_manifest_population_and_materialized_rows() -> None:
    manifest = _load(MANIFEST_PATH)
    migration_pack = _load(PACK_PATH)
    batch = build_batch_dry_run(
        cohort_manifest=manifest,
        migration_packs=[migration_pack],
        source_revision_reference="fixture:nat-p5991-p14143",
    )
    assert batch["schema_version"] == BATCH_RESULT_SCHEMA_VERSION
    assert batch["source_population"] == 37665
    assert batch["materialized_row_count"] == 57
    assert batch["materialized_row_count"] == len(migration_pack["candidates"])
    assert batch["population_fully_materialized"] is False
    assert batch["row_count"] == 57
    assert batch["work_group_count"] == 4
    assert batch["counts_by_first_missing_prerequisite"] == {"source_support": 57}
    assert batch["counts_by_routing_family"] == {"full_auto": 57}
    assert batch["counts_by_selector_class"] == {"zelph_hf_selector": 57}
    assert batch["network_performed"] is False
    assert batch["edits_performed"] is False
    assert batch["consumer_verification_performed"] is False
    assert batch["semantic_promotion_performed"] is False
    assert batch["batch_ref"].startswith("nat-batch-prerequisite:")


def test_batch_content_address_is_deterministic() -> None:
    manifest = {
        "lane_id": "wikidata_nat_wdu_p5991_p14143",
        "cohorts": [
            {"cohort_id": "business_family_reconciled", "population": 37665}
        ],
    }
    pack = {"candidates": [_candidate()]}
    left = build_batch_dry_run(
        cohort_manifest=manifest,
        migration_packs=[pack],
        source_revision_reference="revision:test",
    )
    right = build_batch_dry_run(
        cohort_manifest=manifest,
        migration_packs=[pack],
        source_revision_reference="revision:test",
    )
    assert left["batch_ref"] == right["batch_ref"]
    assert left == right
