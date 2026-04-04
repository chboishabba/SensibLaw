from __future__ import annotations

from src.models import (
    NAT_CLAIM_SCHEMA_VERSION,
    NatClaim,
    NormalizedClaim,
    build_nat_claim_from_candidate,
    build_normalized_claim_from_candidate,
    build_normalized_claim_dict,
)


def test_nat_claim_normalization_preserves_bundle_fields() -> None:
    candidate = {
        "candidate_id": "Q1|P99|1",
        "family_id": "family_sample",
        "cohort_id": "cohort_sample",
        "entity_qid": "Q1",
        "classification": "safe_with_reference_transfer",
        "action": "migrate_with_refs",
        "claim_bundle_before": {
            "subject": "Q1",
            "property": "P99",
            "value": "123",
            "rank": "normal",
            "window_id": "t1",
            "qualifiers": {"P585": ["2024-01-01T00:00:00Z"]},
            "references": [{"P248": ["Qsource"]}],
        },
        "claim_bundle_after": {
            "subject": "Q1",
            "property": "P142",
            "value": "123",
            "rank": "normal",
            "window_id": "t2",
            "qualifiers": {"P585": ["2024-01-01T00:00:00Z"]},
            "references": [{"P248": ["Qsource"]}],
        },
        "root_artifact_id": "artifact-1",
        "source_kind": "openrefine_review_rows",
    }
    claim = build_nat_claim_from_candidate(candidate)
    payload = claim.to_dict()
    assert payload["candidate_id"] == "Q1|P99|1"
    assert payload["family_id"] == "family_sample"
    assert payload["property"] == "P142"
    assert payload["window_id"] == "t2"
    assert payload["qualifiers"]["P585"] == ["2024-01-01T00:00:00Z"]
    assert payload["references"] == [{"P248": ["Qsource"]}]


def test_normalized_claim_aliases_are_additive_and_schema_stable() -> None:
    assert NormalizedClaim is NatClaim

    payload = build_normalized_claim_dict(
        claim_id="Q1|P99|1",
        family_id="family_sample",
        cohort_id="cohort_sample",
        candidate_id="Q1|P99|1",
        canonical_form={
            "subject": "Q1",
            "property": "P142",
            "value": "123",
            "qualifiers": {"P585": ["2024-01-01T00:00:00Z"]},
            "references": [{"P248": ["Qsource"]}],
        },
        source_property="P99",
        target_property="P142",
        state="PROMOTED",
        state_basis="baseline_runtime",
        root_artifact_id="artifact-1",
        provenance={"source_family": "sample"},
        evidence_status="repeated_run",
    )

    assert payload["schema_version"] == NAT_CLAIM_SCHEMA_VERSION
    assert payload["property"] == "P142"
    assert payload["qualifiers"]["P585"] == ["2024-01-01T00:00:00Z"]


def test_build_normalized_claim_from_candidate_reuses_nat_claim_builder() -> None:
    candidate = {
        "candidate_id": "Q1|P99|1",
        "claim_bundle_after": {
            "subject": "Q1",
            "property": "P142",
            "value": "123",
            "qualifiers": {"P585": ["2024-01-01T00:00:00Z"]},
            "references": [{"P248": ["Qsource"]}],
        },
    }

    claim = build_normalized_claim_from_candidate(candidate)
    assert isinstance(claim, NatClaim)
    assert claim.to_dict()["schema_version"] == NAT_CLAIM_SCHEMA_VERSION
