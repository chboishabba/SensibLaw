from __future__ import annotations

from typing import Any, Mapping, Sequence


WIKIDATA_NAT_COHORT_B_REVIEW_BUCKET_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_b_review_bucket.v0_1"
)

EXPECTED_QUALIFIER_PROPERTIES = frozenset(
    {"P459", "P3831", "P585", "P580", "P582", "P518", "P7452"}
)
EXPECTED_REFERENCE_PROPERTIES = frozenset(
    {"P854", "P1065", "P813", "P1476", "P2960"}
)
BUSINESS_FAMILY_INSTANCE_OF = frozenset({"Q4830453", "Q6881511", "Q891723"})


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    items = [_stringify(item) for item in value]
    return sorted({item for item in items if item})


def _row_variance_flags(*, qualifier_properties: Sequence[str], reference_properties: Sequence[str]) -> list[str]:
    qualifier_set = set(qualifier_properties)
    reference_set = set(reference_properties)
    flags: list[str] = []
    if qualifier_set - EXPECTED_QUALIFIER_PROPERTIES:
        flags.append("unexpected_qualifier_properties")
    if EXPECTED_QUALIFIER_PROPERTIES - qualifier_set:
        flags.append("missing_expected_qualifier_properties")
    if reference_set - EXPECTED_REFERENCE_PROPERTIES:
        flags.append("unexpected_reference_properties")
    if EXPECTED_REFERENCE_PROPERTIES - reference_set:
        flags.append("missing_expected_reference_properties")
    if {"P585", "P580", "P582"} <= qualifier_set:
        flags.append("mixed_temporal_qualifier_resolution")
    return sorted(set(flags))


def _reviewer_questions(*, instance_of_qid: str, variance_flags: Sequence[str]) -> list[str]:
    questions = [
        f"Does class {instance_of_qid or 'unknown'} preserve semantic equivalence under P5991 -> P14143 mapping?",
        "Are split axes sufficient to avoid claim-boundary collapse for this row?",
    ]
    flags = set(variance_flags)
    if "unexpected_qualifier_properties" in flags:
        questions.append("Do unexpected qualifier properties represent class-local semantics requiring hold?")
    if "unexpected_reference_properties" in flags:
        questions.append("Do unexpected reference properties change source-trust or citation-shape assumptions?")
    if "mixed_temporal_qualifier_resolution" in flags:
        questions.append("Should temporal qualifiers be normalized before any migration decision?")
    return questions


def build_nat_cohort_b_review_bucket(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("cohort B payload must be an object")
    if _stringify(payload.get("schema_version")) != WIKIDATA_NAT_COHORT_B_REVIEW_BUCKET_SCHEMA_VERSION:
        raise ValueError(
            "cohort B payload must use "
            f"{WIKIDATA_NAT_COHORT_B_REVIEW_BUCKET_SCHEMA_VERSION}"
        )

    rows = payload.get("candidates")
    if not isinstance(rows, list):
        raise ValueError("cohort B payload requires candidates list")

    violations: list[dict[str, str]] = []
    review_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("cohort B candidates must be objects")
        row_id = _stringify(row.get("row_id"))
        entity_qid = _stringify(row.get("entity_qid"))
        instance_of_qid = _stringify(row.get("instance_of_qid"))
        reconciled = bool(row.get("reconciled_instance_of"))

        if not reconciled:
            violations.append(
                {"row_id": row_id, "violation": "unreconciled_instance_of_in_cohort_b_payload"}
            )
            continue
        if instance_of_qid in BUSINESS_FAMILY_INSTANCE_OF:
            violations.append(
                {"row_id": row_id, "violation": "business_family_instance_of_in_cohort_b_payload"}
            )
            continue

        qualifier_properties = _string_list(row.get("qualifier_properties", []))
        reference_properties = _string_list(row.get("reference_properties", []))
        variance_flags = _row_variance_flags(
            qualifier_properties=qualifier_properties,
            reference_properties=reference_properties,
        )
        review_rows.append(
            {
                "row_id": row_id,
                "entity_qid": entity_qid,
                "instance_of_qid": instance_of_qid,
                "review_mode": "review_first",
                "qualifier_properties": qualifier_properties,
                "reference_properties": reference_properties,
                "variance_flags": variance_flags,
                "reviewer_questions": _reviewer_questions(
                    instance_of_qid=instance_of_qid,
                    variance_flags=variance_flags,
                ),
            }
        )

    decision = "review_only"
    decision_reasons: list[str] = []
    if violations:
        decision = "hold"
        decision_reasons.append("payload_contains_rows_outside_cohort_b_contract")
    if not review_rows:
        decision = "hold"
        decision_reasons.append("no_valid_cohort_b_candidates")
    if not decision_reasons:
        decision_reasons.append("cohort_b_rows_require_reviewer_confirmation_before_migration")

    return {
        "schema_version": WIKIDATA_NAT_COHORT_B_REVIEW_BUCKET_SCHEMA_VERSION,
        "lane_id": _stringify(payload.get("lane_id")) or "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "cohort_b_reconciled_non_business",
        "decision": decision,
        "decision_reasons": sorted(set(decision_reasons)),
        "review_bucket_rows": review_rows if decision == "review_only" else [],
        "contract_violations": violations,
        "expected_shape": {
            "qualifier_properties": sorted(EXPECTED_QUALIFIER_PROPERTIES),
            "reference_properties": sorted(EXPECTED_REFERENCE_PROPERTIES),
        },
        "summary": {
            "input_candidate_count": len(rows),
            "valid_review_row_count": len(review_rows),
            "contract_violation_count": len(violations),
            "review_only_row_count": len(review_rows) if decision == "review_only" else 0,
        },
        "non_claims": [
            "review-first bucket only",
            "not migration execution",
            "not full semantic decomposition",
        ],
    }


__all__ = [
    "WIKIDATA_NAT_COHORT_B_REVIEW_BUCKET_SCHEMA_VERSION",
    "build_nat_cohort_b_review_bucket",
]
