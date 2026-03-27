import json
from pathlib import Path

import pytest
import jsonschema
import yaml

from src.sl_projection_boundary import build_wikidata_projection_report


def _base_payload():
    payload = {
        "payload_version": "sl.observation_claim.contract.v1",
        "observations": [
            {
                "observation_id": "obs:1",
                "source_unit_id": "unit:1",
                "source_quote": "Witness stated the contract was signed.",
                "evidence_refs": [{"span_ref": "unit:1:0-34", "ref_type": "text_span"}],
                "payload_version": "sl.observation_claim.contract.v1",
                "hash": "obs-hash",
                "asserted_at": "2026-03-27T00:00:00Z",
                "status": "active",
                "canonicality": "verified",
                "jurisdiction": "US_CA",
            }
        ],
        "claims": [
            {
                "claim_id": "claim:1",
                "observation_id": "obs:1",
                "predicate": "P31",
                "subject_id": "Q100",
                "object_id": "Q200",
                "subject_type": "entity",
                "object_type": "entity",
                "norm_id": "LAW-12",
                "posture": "asserted",
                "evidence_quality": "high",
                "confidence": 0.91,
                "claim_created_at": "2026-03-27T00:01:00Z",
                "claim_updated_at": "2026-03-27T00:01:00Z",
                "evidence_links": ["link:1"],
                "hash": "claim-hash",
            }
        ],
        "evidence_links": [
            {
                "link_id": "link:1",
                "claim_id": "claim:1",
                "observation_id": "obs:1",
                "link_kind": "supporting",
                "span_ref": "span:1",
                "trace_refs": ["receipt:1", "receipt:2"],
                "link_hash": "link-hash",
            }
        ],
        "transition_receipts": [
            {
                "transition_receipt_id": "tr:1",
                "observation_ids": ["obs:1"],
                "current_state": "active",
                "next_state": "active",
                "rule_id": "rule:jurisdiction-check",
                "rule_version": "rule-set-v1",
                "jurisdiction": "US_CA",
                "legal_version": "LAW-12:v20260327",
                "effective_from": "2026-03-27T00:00:00Z",
                "deltas": [
                    {
                        "kind": "jurisdiction",
                        "before": "unknown",
                        "after": "US_CA",
                    }
                ],
            }
        ],
    }

    schema = yaml.safe_load(
        (
            Path(__file__).resolve().parent.parent
            / "schemas"
            / "sl.observation_claim.wikidata_projection.v1.schema.yaml"
        ).read_text(encoding="utf-8")
    )

    contract_schema = yaml.safe_load(
        (
            Path(__file__).resolve().parent.parent
            / "schemas"
            / "sl.observation_claim.contract.v1.schema.yaml"
        ).read_text(encoding="utf-8")
    )
    return payload, schema, contract_schema


def test_observation_claim_wikidata_projection_is_deterministic_and_validates():
    payload, schema, contract_schema = _base_payload()
    jsonschema.validate(payload, contract_schema)
    report = build_wikidata_projection_report(payload)
    jsonschema.validate(report, schema)
    json.dumps(report, sort_keys=True)

    assert report["schema_version"] == "sl.observation_claim.wikidata_projection.v1"
    assert report["projection_summary"]["total_records"] == 1
    assert len(report["projection_records"]) == 1
    assert report["projection_records"][0]["projection_id"] == "wdp:claim:1"
    assert report["projection_records"][0]["evidence_refs"][0]["ref_value"] == "unit:1:0-34"
    assert report["projection_records"][0]["evidence_refs"][-1]["ref_value"] == "receipt:2"
    assert report["projection_records"][0]["state_transition_receipt_ids"] == ["tr:1"]
    assert report["projection_records"][0]["state_transition_receipts"][0]["transition_receipt_id"] == "tr:1"
    assert report["projection_records"][0]["state_transition_receipts"][0]["jurisdiction"] == "US_CA"
    assert report["projection_records"][0]["state_transition_receipts"][0]["legal_version"] == "LAW-12:v20260327"
    assert report["projection_records"][0]["state_transition_receipts"][0]["effective_from"] == "2026-03-27T00:00:00Z"
    assert report["projection_records"][0]["state_transition_receipts"][0]["rule_version"] == "rule-set-v1"
    assert report["projection_records"][0]["temporal_scope"]["observed_at"] is None
    assert report["projection_records"][0]["temporal_scope"]["asserted_at"] == "2026-03-27T00:01:00Z"
    assert report["projection_records"][0]["temporal_scope"]["effective_from"] == "2026-03-27T00:01:00Z"
    assert report["projection_records"][0]["temporal_scope"]["effective_to"] is None
    assert report["projection_records"][0]["provenance"]["jurisdiction"] == "US_CA"
    assert report["projection_summary"]["jurisdiction_count"] == 1
    assert report["projection_summary"]["temporal_scope_records"] == 1
    assert report["projection_summary"]["transition_receipt_count"] == 1
    assert report["projection_summary"]["transition_receipts_with_jurisdiction"] == 1
    assert report["projection_summary"]["transition_receipts_with_legal_version"] == 1


def test_transition_receipt_rejects_effective_to_before_effective_from():
    payload, _, contract_schema = _base_payload()
    payload["transition_receipts"][0]["effective_from"] = "2026-03-27T12:00:00Z"
    payload["transition_receipts"][0]["effective_to"] = "2026-03-27T11:59:59Z"
    jsonschema.validate(payload, contract_schema)
    with pytest.raises(ValueError, match="effective_to must be greater than or equal to effective_from"):
        build_wikidata_projection_report(payload)


def test_transition_receipts_reject_temporal_overlap_for_same_observation():
    payload, _, contract_schema = _base_payload()
    payload["transition_receipts"].append(
        {
            "transition_receipt_id": "tr:2",
            "observation_ids": ["obs:1"],
            "current_state": "active",
            "next_state": "active",
            "rule_id": "rule:jurisdiction-check",
            "rule_version": "rule-set-v1",
            "jurisdiction": "US_CA",
            "legal_version": "LAW-12:v20260327",
            "effective_from": "2026-03-27T00:30:00Z",
            "effective_to": "2026-03-27T01:30:00Z",
            "deltas": [
                {
                    "kind": "jurisdiction",
                    "before": "US_CA",
                    "after": "US_CA",
                }
            ],
        }
    )
    jsonschema.validate(payload, contract_schema)
    with pytest.raises(ValueError, match="temporal windows for obs:1 must be non-overlapping"):
        build_wikidata_projection_report(payload)


def test_transition_receipt_rejects_jurisdiction_mismatch_with_claim():
    payload, _, contract_schema = _base_payload()
    payload["observations"][0]["jurisdiction"] = "US_NY"
    jsonschema.validate(payload, contract_schema)
    with pytest.raises(ValueError, match="have mismatched jurisdictions"):
        build_wikidata_projection_report(payload)


def test_transition_receipt_allows_hierarchical_jurisdiction_match():
    payload, _, contract_schema = _base_payload()
    payload["transition_receipts"][0]["jurisdiction"] = "US"
    jsonschema.validate(payload, contract_schema)
    report = build_wikidata_projection_report(payload)

    assert report["projection_records"][0]["state_transition_receipts"][0]["jurisdiction"] == "US"


def test_transition_receipt_rejects_nonhierarchical_jurisdiction_mismatch():
    payload, _, contract_schema = _base_payload()
    payload["transition_receipts"][0]["jurisdiction"] = "US_TX"
    jsonschema.validate(payload, contract_schema)
    with pytest.raises(ValueError, match="have mismatched jurisdictions"):
        build_wikidata_projection_report(payload)


def test_transition_receipt_rejects_legal_version_mismatch_with_claim_norm():
    payload, _, contract_schema = _base_payload()
    payload["claims"][0]["norm_id"] = "LAW-99"
    jsonschema.validate(payload, contract_schema)
    with pytest.raises(ValueError, match="inconsistent with transition receipt"):
        build_wikidata_projection_report(payload)


def test_transition_receipt_rejects_unknown_observation_id():
    payload, _, contract_schema = _base_payload()
    payload["transition_receipts"][0]["observation_ids"] = ["obs:missing"]
    jsonschema.validate(payload, contract_schema)
    with pytest.raises(ValueError, match="references unknown observation obs:missing"):
        build_wikidata_projection_report(payload)


def test_transition_receipts_are_stably_ordered_by_effective_from():
    payload, _, contract_schema = _base_payload()
    payload["transition_receipts"][0]["effective_from"] = "2026-03-27T01:00:00Z"
    payload["transition_receipts"][0]["transition_receipt_id"] = "tr:late"
    payload["transition_receipts"].append(
        {
            "transition_receipt_id": "tr:early",
            "observation_ids": ["obs:1"],
            "current_state": "active",
            "next_state": "active",
            "rule_id": "rule:jurisdiction-check",
            "rule_version": "rule-set-v1",
            "jurisdiction": "US_CA",
            "legal_version": "LAW-12:v20260327",
            "effective_from": "2026-03-27T00:00:00Z",
            "effective_to": "2026-03-27T00:30:00Z",
            "deltas": [
                {
                    "kind": "jurisdiction",
                    "before": "US_CA",
                    "after": "US_CA",
                }
            ],
        }
    )
    jsonschema.validate(payload, contract_schema)
    report = build_wikidata_projection_report(payload)

    assert report["projection_records"][0]["state_transition_receipt_ids"] == [
        "tr:early",
        "tr:late",
    ]
