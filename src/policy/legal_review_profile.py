from __future__ import annotations

from typing import Any, Mapping

from src.ingestion.media_adapter import CanonicalUnit, ParsedEnvelope
from src.models.review_claim_record import build_review_claim_record_dict
from src.policy.candidate_surface import build_candidate_surface
from src.policy.text_surface import build_text_surface


LEGAL_REVIEW_SCHEMA_VERSION = "sl.legal_review_extract.v0_1"


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _unit_text_ref(parsed_envelope: ParsedEnvelope, unit: CanonicalUnit) -> dict[str, Any]:
    return {
        "text_id": parsed_envelope.canonical_text.text_id,
        "segment_id": unit.segment_id,
        "unit_id": unit.unit_id,
        "envelope_id": parsed_envelope.envelope_id,
    }


def build_legal_review_extract(
    parsed_envelope: ParsedEnvelope,
    *,
    lane: str,
    family_id: str,
    cohort_id: str,
    root_artifact_id: str,
    source_family: str,
    source_kind: str = "legal_review_source",
    singleton_target_hint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    review_claim_records: list[dict[str, Any]] = []
    lane_value = _clean_text(lane) or "legal"
    family_value = _clean_text(family_id) or f"{lane_value}_legal_review"
    cohort_value = _clean_text(cohort_id) or parsed_envelope.envelope_id
    root_value = _clean_text(root_artifact_id) or parsed_envelope.canonical_text.text_id
    source_family_value = _clean_text(source_family) or family_value
    source_kind_value = _clean_text(source_kind) or "legal_review_source"

    for unit in parsed_envelope.parsed_units:
        text = _clean_text(unit.text)
        if not text:
            continue
        text_ref = _unit_text_ref(parsed_envelope, unit)
        anchor_refs = {
            **dict(unit.anchor_refs),
            "parse_profile": parsed_envelope.parse_profile,
        }
        claim_id = f"{parsed_envelope.canonical_text.text_id}:review_claim:{unit.unit_id}"
        review_text = build_text_surface(
            text=text,
            source_kind=source_kind_value,
            text_role="parsed_unit_text",
            anchor_refs=anchor_refs,
            text_ref=text_ref,
        )
        review_candidate = None
        if isinstance(singleton_target_hint, Mapping) and singleton_target_hint:
            candidate_id = _clean_text(singleton_target_hint.get("candidate_id"))
            candidate_kind = _clean_text(singleton_target_hint.get("candidate_kind"))
            if candidate_id and candidate_kind:
                review_candidate = build_candidate_surface(
                    candidate_id=candidate_id,
                    candidate_kind=candidate_kind,
                    source_kind=source_kind_value,
                    selection_basis={
                        "selection_mode": "explicit_singleton_hint",
                        "parse_profile": parsed_envelope.parse_profile,
                    },
                    anchor_refs=anchor_refs,
                )

        review_claim_records.append(
            build_review_claim_record_dict(
                claim_id=claim_id,
                candidate_id=claim_id,
                family_id=family_value,
                cohort_id=cohort_value,
                root_artifact_id=root_value,
                lane=lane_value,
                source_family=source_family_value,
                state="review_claim",
                state_basis="parsed_envelope_unit",
                evidence_status="review_only",
                review_candidate=review_candidate,
                review_text=review_text,
                provenance={
                    "text_id": parsed_envelope.canonical_text.text_id,
                    "envelope_id": parsed_envelope.envelope_id,
                    "parse_profile": parsed_envelope.parse_profile,
                    "parse_receipt": {
                        "parser_version": parsed_envelope.parse_receipt.get(
                            "parser_version"
                        ),
                        "segment_count": parsed_envelope.parse_receipt.get(
                            "segment_count"
                        ),
                        "unit_count": parsed_envelope.parse_receipt.get("unit_count"),
                    },
                },
                decision_basis={
                    "unit_kind": unit.unit_kind,
                    "parse_profile": parsed_envelope.parse_profile,
                },
                review_route={
                    "recommended_view": "parsed_review_text",
                    "actionability": "must_review",
                },
            )
        )

    return {
        "schema_version": LEGAL_REVIEW_SCHEMA_VERSION,
        "parse_profile": "legal_review",
        "text_id": parsed_envelope.canonical_text.text_id,
        "envelope_id": parsed_envelope.envelope_id,
        "parser_receipt": {
            "parser_version": parsed_envelope.parse_receipt.get("parser_version"),
            "parse_profile": parsed_envelope.parse_receipt.get("parse_profile"),
            "segment_count": parsed_envelope.parse_receipt.get("segment_count"),
            "unit_count": parsed_envelope.parse_receipt.get("unit_count"),
        },
        "review_claim_records": review_claim_records,
    }
__all__ = [
    "LEGAL_REVIEW_SCHEMA_VERSION",
    "build_legal_review_extract",
]
