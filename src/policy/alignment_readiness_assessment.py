from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.models.equivalence_assessment import build_equivalence_assessment_dict
from src.models.lane_semantics_profile import build_lane_semantics_profile_dict
from src.policy.review_claim_records import build_gwb_targeting_results_from_review_claim_records
from src.policy.review_targeting_contract import (
    assess_gwb_semantic_separability,
    normalize_gwb_target_split_kind,
)

_LANE_INTERPRETATION_KIND = {
    "affidavit": "alignment",
    "gwb": "alignment",
    "au": "routing",
}

_LANE_CARDINALITY_MODE = {
    "affidavit": "singleton",
    "gwb": "singleton",
    "au": "set",
}

_LANE_SEMANTIC_NOTE = {
    "affidavit": "proposition aligns to best source row",
    "gwb": "review item links to source via seed-bounded targeting",
    "au": "review queue row targets an event subset",
}

_TARGET_KIND_BY_BASIS = {
    "best_source_row_id": "source_row",
    "seed_id": "source_row",
    "event_id": "event_subset",
}
_ORIGIN_SEMANTICS_RELATION_GROUPS = (
    frozenset({"affidavit_proposition_row", "source_review_row"}),
    frozenset({"review_queue_row", "event_subset"}),
)


def _normalized_basis_vocab_for_record(record: Mapping[str, Any], lane: str) -> list[str]:
    review_candidate = _as_mapping(record.get("review_candidate"))
    selection_basis = _as_mapping(review_candidate.get("selection_basis"))
    vocabulary: list[str] = []
    if lane == "affidavit":
        if str(selection_basis.get("best_match_basis") or "").strip():
            vocabulary.append("source_row_selection")
    elif lane == "gwb":
        if str(record.get("target_proposition_identity") or ""):
            vocabulary.append("seed_target_selection")
        elif str(selection_basis.get("targeting_mode") or "").strip():
            vocabulary.append("seed_target_selection")
    elif lane == "au":
        if str(record.get("target_proposition_identity") or ""):
            vocabulary.append("event_subset_selection")
    if str(review_candidate.get("target_proposition_id") or "").strip():
        vocabulary.append("target_anchor_present")
    if not vocabulary:
        vocabulary.append("lane_local_other")
    return vocabulary


def review_alignment_emission_allowed(*, equivalence_assessment: Mapping[str, Any]) -> bool:
    """Gate any future shared emitted alignment surface on a promote verdict."""
    return str(equivalence_assessment.get("verdict") or "").strip() == "promote"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _append_if_text(target: list[str], value: Any) -> None:
    text = str(value or "").strip()
    if text:
        target.append(text)


def _source_semantics_shared(left_origin: set[str], right_origin: set[str]) -> bool:
    if left_origin & right_origin:
        return True
    for group in _ORIGIN_SEMANTICS_RELATION_GROUPS:
        if left_origin & group and right_origin & group:
            return True
    return False


def _gwb_cardinality_mode(review_item_rows: Sequence[Mapping[str, Any]]) -> str:
    candidate_counts_by_seed: dict[str, int] = {}
    for row in review_item_rows:
        if not isinstance(row, Mapping):
            continue
        seed_id = str(row.get("seed_id") or "").strip()
        review_item_id = str(row.get("review_item_id") or "").strip()
        if not seed_id or not review_item_id:
            continue
        candidate_counts_by_seed[seed_id] = candidate_counts_by_seed.get(seed_id, 0) + 1
    if not candidate_counts_by_seed:
        return _LANE_CARDINALITY_MODE["gwb"]
    unique_counts = set(candidate_counts_by_seed.values())
    if unique_counts == {1}:
        return "singleton"
    if all(count > 1 for count in unique_counts):
        return "set"
    return "mixed"


def build_lane_semantics_profile_from_review_claim_records(
    *,
    lane: str,
    family_id: str,
    review_claim_records: Sequence[Mapping[str, Any]],
    review_item_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    origin_kinds: list[str] = []
    target_kinds: list[str] = []
    basis_vocabulary: list[str] = []
    relation_kinds: list[str] = []
    text_roles: list[str] = []
    anchor_ref_keys: list[str] = []
    semantic_notes: list[str] = []
    for record in review_claim_records:
        if not isinstance(record, Mapping):
            continue
        proposition_identity = _as_mapping(record.get("proposition_identity"))
        identity_basis = _as_mapping(proposition_identity.get("identity_basis"))
        _append_if_text(origin_kinds, identity_basis.get("basis_kind"))

        target_identity = _as_mapping(record.get("target_proposition_identity"))
        target_basis = _as_mapping(target_identity.get("identity_basis"))
        target_basis_kind = str(target_basis.get("basis_kind") or "").strip()
        if target_basis_kind:
            target_kinds.append(_TARGET_KIND_BY_BASIS.get(target_basis_kind, target_basis_kind))

        basis_vocabulary.extend(_normalized_basis_vocab_for_record(record, lane))

        proposition_relation = _as_mapping(record.get("proposition_relation"))
        _append_if_text(relation_kinds, proposition_relation.get("relation_kind"))

        review_text = _as_mapping(record.get("review_text"))
        _append_if_text(text_roles, review_text.get("text_role"))

        review_candidate = _as_mapping(record.get("review_candidate"))
        review_candidate_anchor_refs = _as_mapping(review_candidate.get("anchor_refs"))
        anchor_ref_keys.extend(str(key) for key in review_candidate_anchor_refs.keys() if str(key).strip())

    cardinality_mode = _LANE_CARDINALITY_MODE.get(lane, "mixed")
    if lane == "gwb" and review_item_rows is not None:
        cardinality_mode = _gwb_cardinality_mode(review_item_rows)
        targeting_results = build_gwb_targeting_results_from_review_claim_records(
            review_claim_records=review_claim_records,
            review_item_rows=review_item_rows,
        )
        for result in targeting_results:
            assessment = assess_gwb_semantic_separability(result=result)
            assessment_status = str(assessment.get("assessment_status") or "").strip()
            if assessment_status and assessment_status != "not_applicable":
                semantic_notes.append(f"semantic_separability:{assessment_status}")
            reason_codes = [
                str(value).strip()
                for value in assessment.get("reason_codes", [])
                if str(value).strip()
            ]
            semantic_notes.extend(f"semantic_reason:{value}" for value in reason_codes)
            for candidate in result.candidate_targets:
                normalized_split = normalize_gwb_target_split_kind(candidate.target_split_kind)
                if normalized_split != "no_split":
                    semantic_notes.append(f"normalized_split:{normalized_split}")

    return build_lane_semantics_profile_dict(
        lane=lane,
        family_id=family_id,
        origin_kinds=origin_kinds,
        target_kinds=target_kinds,
        cardinality_mode=cardinality_mode,
        basis_vocabulary=basis_vocabulary,
        interpretation_kind=_LANE_INTERPRETATION_KIND.get(lane, "lane_local_other"),
        descriptive_only=True,
        control_leakage_risk=False,
        relation_kinds=relation_kinds,
        text_roles=text_roles,
        anchor_ref_keys=anchor_ref_keys,
        semantic_notes=[
            _LANE_SEMANTIC_NOTE.get(lane, "lane-local targeting semantics"),
            *semantic_notes,
        ],
    )


def assess_lane_semantics_equivalence(
    *,
    left_profile: Mapping[str, Any],
    right_profile: Mapping[str, Any],
) -> dict[str, Any]:
    left_origin = set(str(value) for value in left_profile.get("origin_kinds", []) if str(value).strip())
    right_origin = set(str(value) for value in right_profile.get("origin_kinds", []) if str(value).strip())
    left_target = set(str(value) for value in left_profile.get("target_kinds", []) if str(value).strip())
    right_target = set(str(value) for value in right_profile.get("target_kinds", []) if str(value).strip())
    left_vocab = set(str(value) for value in left_profile.get("basis_vocabulary", []) if str(value).strip())
    right_vocab = set(str(value) for value in right_profile.get("basis_vocabulary", []) if str(value).strip())

    literal_source_semantics_shared = bool(left_origin & right_origin)
    source_semantics_shared = _source_semantics_shared(left_origin, right_origin)
    target_semantics_shared = bool(left_target & right_target)
    basis_vocabulary_shared = bool(left_vocab & right_vocab)
    cardinality_shared = str(left_profile.get("cardinality_mode") or "") == str(
        right_profile.get("cardinality_mode") or ""
    )
    interpretation_shared = str(left_profile.get("interpretation_kind") or "") == str(
        right_profile.get("interpretation_kind") or ""
    )
    descriptive_only_shared = bool(left_profile.get("descriptive_only")) and bool(
        right_profile.get("descriptive_only")
    )
    control_leakage_risk = bool(left_profile.get("control_leakage_risk")) or bool(
        right_profile.get("control_leakage_risk")
    )

    notes: list[str] = []
    if target_semantics_shared:
        notes.append("shared target semantics")
    if source_semantics_shared and not literal_source_semantics_shared:
        notes.append("source semantics shared via bounded relation map")
    if basis_vocabulary_shared:
        notes.append("shared bounded selection vocabulary")
    if interpretation_shared:
        notes.append("shared interpretation kind")
    if cardinality_shared:
        notes.append("shared cardinality mode")

    if (
        literal_source_semantics_shared
        and target_semantics_shared
        and basis_vocabulary_shared
        and cardinality_shared
        and interpretation_shared
        and descriptive_only_shared
        and not control_leakage_risk
    ):
        verdict = "promote"
    elif (
        target_semantics_shared
        and basis_vocabulary_shared
        and interpretation_shared
        and descriptive_only_shared
        and not control_leakage_risk
    ):
        verdict = "prototype_only"
    else:
        verdict = "hold"

    return build_equivalence_assessment_dict(
        left_lane=str(left_profile.get("lane") or "").strip(),
        right_lane=str(right_profile.get("lane") or "").strip(),
        source_semantics_shared=source_semantics_shared,
        target_semantics_shared=target_semantics_shared,
        basis_vocabulary_shared=basis_vocabulary_shared,
        cardinality_shared=cardinality_shared,
        interpretation_shared=interpretation_shared,
        descriptive_only_shared=descriptive_only_shared,
        control_leakage_risk=control_leakage_risk,
        notes=notes,
        verdict=verdict,
    )
