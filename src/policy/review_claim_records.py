from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.models.proposition_identity import build_proposition_identity_dict
from src.models.proposition_relation import build_proposition_relation_dict
from src.models.review_claim_record import build_review_candidate_dict, build_review_claim_record_dict
from src.policy.review_targeting_contract import GWBTargetingCandidate, GWBTargetingResult, build_gwb_targeting_result


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _build_review_text(
    *,
    text: Any,
    text_role: str,
    source_kind: str,
    anchor_refs: Mapping[str, Any] | None = None,
    text_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    rendered = _clean_text(text)
    if not rendered:
        return None
    payload: dict[str, Any] = {
        "text": rendered,
        "text_role": text_role,
        "source_kind": source_kind,
    }
    clean_anchor_refs = {
        str(key): value
        for key, value in (anchor_refs or {}).items()
        if value not in (None, "", [], {})
    }
    if clean_anchor_refs:
        payload["anchor_refs"] = clean_anchor_refs
    clean_text_ref = {
        str(key): value
        for key, value in (text_ref or {}).items()
        if value not in (None, "", [], {})
    }
    if clean_text_ref:
        payload["text_ref"] = clean_text_ref
    return payload


def _build_text_ref(row: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        return {}

    explicit = row.get("text_ref")
    if isinstance(explicit, Mapping):
        return {
            str(key): value
            for key, value in explicit.items()
            if value not in (None, "", [], {})
        }

    return {
        str(key): value
        for key, value in {
            "text_id": row.get("text_id"),
            "segment_id": row.get("segment_id"),
            "unit_id": row.get("unit_id"),
            "envelope_id": row.get("envelope_id"),
        }.items()
        if value not in (None, "", [], {})
    }


def _build_review_candidate(
    *,
    candidate_id: Any,
    candidate_kind: str,
    source_kind: Any,
    selection_basis: Mapping[str, Any] | None = None,
    anchor_refs: Mapping[str, Any] | None = None,
    target_proposition_id: Any | None = None,
) -> dict[str, Any]:
    return build_review_candidate_dict(
        candidate_id=str(candidate_id or "").strip(),
        candidate_kind=candidate_kind,
        source_kind=str(source_kind or "").strip(),
        selection_basis={
            str(key): value
            for key, value in (selection_basis or {}).items()
            if value not in (None, "", [], {})
        },
        anchor_refs={
            str(key): value
            for key, value in (anchor_refs or {}).items()
            if value not in (None, "", [], {})
        },
        target_proposition_id=target_proposition_id,
    )


def _copy_kind_value_refs(values: Any) -> list[dict[str, Any]] | None:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return None

    copied: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            return None
        kind = _clean_text(value.get("kind"))
        ref_value = _clean_text(value.get("value"))
        if not kind or not ref_value:
            return None
        copied.append(
            {
                str(key): item
                for key, item in value.items()
                if item not in (None, "", [], {})
            }
        )
        copied[-1]["kind"] = kind
        copied[-1]["value"] = ref_value
    return copied


def build_review_candidate_from_composed_candidate_node(
    candidate: Mapping[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(candidate, Mapping):
        return None

    candidate_kind = _clean_text(candidate.get("kind")) or "composed_candidate_node"
    predicate_family = _clean_text(candidate.get("predicate_family"))
    status = _clean_text(candidate.get("status"))
    section = _clean_text(candidate.get("section"))
    genre = _clean_text(candidate.get("genre"))
    support_phi_values = candidate.get("support_phi_ids", [])
    if not isinstance(support_phi_values, Sequence) or isinstance(support_phi_values, (str, bytes)):
        support_phi_values = []
    support_phi_ids = [
        cleaned
        for cleaned in (_clean_text(value) for value in support_phi_values)
        if cleaned
    ]
    content_refs = _copy_kind_value_refs(candidate.get("content_refs"))
    authority_wrapper = candidate.get("authority_wrapper")
    span_refs = _copy_kind_value_refs(candidate.get("span_refs"))
    provenance_receipts = _copy_kind_value_refs(candidate.get("provenance_receipts"))
    if (
        not predicate_family
        or not status
        or not section
        or not genre
        or not support_phi_ids
        or not content_refs
        or not isinstance(authority_wrapper, Mapping)
        or not _clean_text(authority_wrapper.get("kind") or authority_wrapper.get("wrapper_kind"))
        or not span_refs
        or not provenance_receipts
    ):
        return None

    wrapper_kind = _clean_text(
        authority_wrapper.get("kind")
        or authority_wrapper.get("wrapper_kind")
        or authority_wrapper.get("authority_kind")
    )
    wrapper_status = _clean_text(
        authority_wrapper.get("status")
        or authority_wrapper.get("decision")
        or authority_wrapper.get("validity")
    )
    candidate_id = support_phi_ids[0]
    selection_basis: dict[str, Any] = {
        "basis_kind": "composed_candidate_node",
        "predicate_family": predicate_family,
        "status": status,
        "section": section,
        "genre": genre,
        "support_phi_count": len(support_phi_ids),
        "content_ref_count": len(content_refs),
        "span_ref_count": len(span_refs),
        "provenance_receipt_count": len(provenance_receipts),
    }
    if wrapper_kind:
        selection_basis["authority_wrapper_kind"] = wrapper_kind
    if wrapper_status:
        selection_basis["authority_wrapper_status"] = wrapper_status

    return build_review_candidate_dict(
        candidate_id=candidate_id,
        candidate_kind=candidate_kind,
        source_kind="composed_candidate_node",
        selection_basis=selection_basis,
        anchor_refs={
            "support_phi_ids": support_phi_ids,
            "content_refs": content_refs,
            "span_refs": span_refs,
            "provenance_receipts": provenance_receipts,
        },
    )


def _build_review_candidate_for_review_row(
    *,
    row: Mapping[str, Any],
    claim_id: str,
    basis_kind: str,
    review_status: str,
) -> dict[str, Any]:
    composed_candidate = row.get("composed_candidate_node")
    if isinstance(composed_candidate, Mapping):
        review_candidate = build_review_candidate_from_composed_candidate_node(composed_candidate)
        if review_candidate is not None:
            return review_candidate
    return _build_review_candidate(
        candidate_id=claim_id,
        candidate_kind="review_source_row",
        source_kind=str(row.get("source_kind") or "").strip() or "source_review_row",
        selection_basis={
            "basis_kind": basis_kind,
            "review_status": review_status,
            "primary_workload_class": str(row.get("primary_workload_class") or "").strip(),
            "linkage_kind": str(row.get("linkage_kind") or "").strip(),
        },
        anchor_refs={
            "source_row_id": claim_id,
            "seed_id": str(row.get("seed_id") or "").strip(),
        },
    )


def build_affidavit_target_proposition_identity(
    *,
    row: Mapping[str, Any],
    lane: str,
    family_id: str,
    cohort_id: str,
    root_artifact_id: str,
    source_family: str,
) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    best_source_row_id = str(row.get("best_source_row_id") or "").strip()
    if not best_source_row_id:
        return None
    proposition_id = f"{lane}_source_row_prop:{cohort_id}:{best_source_row_id}"
    return build_proposition_identity_dict(
        proposition_id=proposition_id,
        family_id=family_id,
        cohort_id=cohort_id,
        root_artifact_id=root_artifact_id,
        lane=lane,
        source_family=source_family,
        basis_kind="best_source_row_id",
        local_id=best_source_row_id,
        source_kind="affidavit_source_row_target",
        upstream_artifact_ids=[
            value
            for value in (root_artifact_id, cohort_id)
            if isinstance(value, str) and value.strip()
        ],
        anchor_refs={
            "best_source_row_id": best_source_row_id,
            "proposition_id": str(row.get("proposition_id") or "").strip(),
            "best_match_basis": str(row.get("best_match_basis") or "").strip(),
        },
    )


def build_affidavit_proposition_relation(
    *,
    row: Mapping[str, Any],
    lane: str,
    family_id: str,
    cohort_id: str,
    root_artifact_id: str,
    source_family: str,
    relation_kind: str = "addresses",
) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    proposition_id = str(row.get("proposition_id") or "").strip()
    if not proposition_id:
        return None
    target_identity = build_affidavit_target_proposition_identity(
        row=row,
        lane=lane,
        family_id=family_id,
        cohort_id=cohort_id,
        root_artifact_id=root_artifact_id,
        source_family=source_family,
    )
    if not isinstance(target_identity, Mapping) or not target_identity:
        return None
    best_source_row_id = str(
        (
            target_identity.get("provenance")
            if isinstance(target_identity.get("provenance"), Mapping)
            else {}
        ).get("anchor_refs", {})
        .get("best_source_row_id", "")
    ).strip()
    if not best_source_row_id:
        return None
    return build_proposition_relation_dict(
        relation_id=f"{lane}_review_rel:{cohort_id}:{proposition_id}:{relation_kind}:{best_source_row_id}",
        source_proposition_id=proposition_id,
        target_proposition_id=str(target_identity.get("proposition_id") or "").strip(),
        relation_kind=relation_kind,
        evidence_status="review_only",
        source_kind="affidavit_rows",
        upstream_artifact_ids=[
            value
            for value in (root_artifact_id, cohort_id)
            if isinstance(value, str) and value.strip()
        ],
        anchor_refs={
            "proposition_id": proposition_id,
            "best_source_row_id": best_source_row_id,
            "best_match_basis": str(row.get("best_match_basis") or "").strip(),
        },
    )


def build_review_queue_target_proposition_identity(
    *,
    row: Mapping[str, Any],
    lane: str,
    family_id: str,
    cohort_id: str,
    root_artifact_id: str,
    source_family: str,
) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    event_ids = [
        str(value)
        for value in row.get("event_ids", [])
        if isinstance(value, str) and str(value).strip()
    ]
    if len(event_ids) != 1:
        return None
    event_id = event_ids[0]
    proposition_id = f"{lane}_event_prop:{cohort_id}:{event_id}"
    return build_proposition_identity_dict(
        proposition_id=proposition_id,
        family_id=family_id,
        cohort_id=cohort_id,
        root_artifact_id=root_artifact_id,
        lane=lane,
        source_family=source_family,
        basis_kind="event_id",
        local_id=event_id,
        source_kind="review_bundle_target",
        upstream_artifact_ids=[
            value
            for value in (root_artifact_id, cohort_id)
            if isinstance(value, str) and value.strip()
        ],
        anchor_refs={
            "event_id": event_id,
            "source_ids": [
                str(value)
                for value in row.get("source_ids", [])
                if isinstance(value, str) and str(value).strip()
            ],
            "statement_ids": [
                str(value)
                for value in row.get("statement_ids", [])
                if isinstance(value, str) and str(value).strip()
            ],
        },
    )


def build_review_queue_proposition_relation(
    *,
    row: Mapping[str, Any],
    claim_id: str,
    lane: str,
    family_id: str,
    cohort_id: str,
    root_artifact_id: str,
    source_family: str,
    relation_kind: str = "addresses",
) -> dict[str, Any] | None:
    target_identity = build_review_queue_target_proposition_identity(
        row=row,
        lane=lane,
        family_id=family_id,
        cohort_id=cohort_id,
        root_artifact_id=root_artifact_id,
        source_family=source_family,
    )
    if not isinstance(target_identity, Mapping) or not target_identity:
        return None
    event_id = str(
        (
            target_identity.get("provenance")
            if isinstance(target_identity.get("provenance"), Mapping)
            else {}
        ).get("anchor_refs", {})
        .get("event_id", "")
    ).strip()
    if not event_id:
        return None
    return build_proposition_relation_dict(
        relation_id=f"{lane}_review_rel:{cohort_id}:{claim_id}:{relation_kind}:{event_id}",
        source_proposition_id=claim_id,
        target_proposition_id=str(target_identity.get("proposition_id") or "").strip(),
        relation_kind=relation_kind,
        evidence_status="review_only",
        source_kind="review_bundle",
        upstream_artifact_ids=[
            value
            for value in (root_artifact_id, cohort_id)
            if isinstance(value, str) and value.strip()
        ],
        anchor_refs={
            "fact_id": claim_id,
            "event_id": event_id,
            "source_ids": [
                str(value)
                for value in row.get("source_ids", [])
                if isinstance(value, str) and str(value).strip()
            ],
            "statement_ids": [
                str(value)
                for value in row.get("statement_ids", [])
                if isinstance(value, str) and str(value).strip()
            ],
        },
    )


def build_review_item_target_proposition_identity(
    *,
    seed_id: str,
    review_item_id: str,
    lane: str,
    family_id: str,
    cohort_id: str,
    root_artifact_id: str,
    source_family: str,
) -> dict[str, Any] | None:
    normalized_seed_id = str(seed_id or "").strip()
    if not normalized_seed_id:
        return None
    return build_proposition_identity_dict(
        proposition_id=f"{lane}_review_item_prop:{cohort_id}:{normalized_seed_id}",
        family_id=family_id,
        cohort_id=cohort_id,
        root_artifact_id=root_artifact_id,
        lane=lane,
        source_family=source_family,
        basis_kind="seed_id",
        local_id=normalized_seed_id,
        source_kind="review_item_target",
        upstream_artifact_ids=[
            value
            for value in (root_artifact_id, cohort_id)
            if isinstance(value, str) and value.strip()
        ],
        anchor_refs={
            "seed_id": normalized_seed_id,
            "review_item_id": str(review_item_id or "").strip(),
        },
    )


def attach_review_item_relations_by_seed_id(
    *,
    review_claim_records: Sequence[Mapping[str, Any]],
    review_item_rows: Sequence[Mapping[str, Any]],
    relation_kind: str = "addresses",
) -> list[dict[str, Any]]:
    targeting_results = build_gwb_targeting_results_from_review_claim_records(
        review_claim_records=review_claim_records,
        review_item_rows=review_item_rows,
        relation_kind=relation_kind,
    )
    targeting_results_by_claim_id = {
        str(result.claim_id or "").strip(): result
        for result in targeting_results
        if str(result.claim_id or "").strip()
    }
    attached_records: list[dict[str, Any]] = []
    for record in review_claim_records:
        copied = dict(record)
        if copied.get("target_proposition_identity") or copied.get("proposition_relation"):
            attached_records.append(copied)
            continue
        targeting_result = targeting_results_by_claim_id.get(str(copied.get("claim_id") or "").strip())
        proposition_identity = copied.get("proposition_identity") if isinstance(copied.get("proposition_identity"), Mapping) else {}
        proposition_identity_provenance = (
            proposition_identity.get("provenance")
            if isinstance(proposition_identity.get("provenance"), Mapping)
            else {}
        )
        anchor_refs = (
            proposition_identity_provenance.get("anchor_refs")
            if isinstance(proposition_identity_provenance.get("anchor_refs"), Mapping)
            else {}
        )
        seed_id = str(anchor_refs.get("seed_id") or copied.get("provenance", {}).get("seed_id") or "").strip()
        if targeting_result and targeting_result.selection_mode != "singleton_seed_linkage":
            review_candidate = copied.get("review_candidate")
            if isinstance(review_candidate, Mapping):
                review_candidate_payload = dict(review_candidate)
                selection_basis = (
                    review_candidate_payload.get("selection_basis")
                    if isinstance(review_candidate_payload.get("selection_basis"), Mapping)
                    else {}
                )
                review_candidate_payload["selection_basis"] = {
                    **dict(selection_basis),
                    "targeting_mode": targeting_result.selection_mode,
                    "candidate_count": targeting_result.candidate_count,
                }
                copied["review_candidate"] = review_candidate_payload
        if not seed_id or not targeting_result.selected_target:
            attached_records.append(copied)
            continue
        selected_target = targeting_result.selected_target
        target_identity = dict(selected_target.target_proposition_identity)
        copied["target_proposition_identity"] = dict(target_identity)
        review_candidate = copied.get("review_candidate")
        if isinstance(review_candidate, Mapping):
            review_candidate_payload = dict(review_candidate)
            target_proposition_id = str(target_identity.get("proposition_id") or "").strip()
            if target_proposition_id:
                review_candidate_payload["target_proposition_id"] = target_proposition_id
            copied["review_candidate"] = review_candidate_payload
        copied["proposition_relation"] = build_proposition_relation_dict(
            relation_id=(
                f"{copied.get('lane')}_review_rel:{copied.get('cohort_id')}:"
                f"{copied.get('claim_id')}:{relation_kind}:{seed_id}"
            ),
            source_proposition_id=str(proposition_identity.get("proposition_id") or copied.get("claim_id") or ""),
            target_proposition_id=str(target_identity.get("proposition_id") or ""),
            relation_kind=relation_kind,
            evidence_status="review_only",
            source_kind="review_item_rows",
            upstream_artifact_ids=[
                value
                for value in (copied.get("root_artifact_id"), copied.get("cohort_id"))
                if isinstance(value, str) and value.strip()
            ],
            anchor_refs={
                "claim_id": str(copied.get("claim_id") or ""),
                "seed_id": seed_id,
                "review_item_id": selected_target.review_item_id,
            },
        )
        attached_records.append(copied)
    return attached_records


def build_gwb_targeting_results_from_review_claim_records(
    *,
    review_claim_records: Sequence[Mapping[str, Any]],
    review_item_rows: Sequence[Mapping[str, Any]],
    relation_kind: str = "addresses",
) -> list[GWBTargetingResult]:
    review_items_by_seed: dict[str, list[Mapping[str, Any]]] = {}
    for row in review_item_rows:
        if not isinstance(row, Mapping):
            continue
        seed_id = str(row.get("seed_id") or "").strip()
        review_item_id = str(row.get("review_item_id") or "").strip()
        if seed_id and review_item_id:
            review_items_by_seed.setdefault(seed_id, []).append(row)

    targeting_results = []
    for record in review_claim_records:
        if not isinstance(record, Mapping):
            continue
        proposition_identity = (
            record.get("proposition_identity")
            if isinstance(record.get("proposition_identity"), Mapping)
            else {}
        )
        proposition_identity_provenance = (
            proposition_identity.get("provenance")
            if isinstance(proposition_identity.get("provenance"), Mapping)
            else {}
        )
        anchor_refs = (
            proposition_identity_provenance.get("anchor_refs")
            if isinstance(proposition_identity_provenance.get("anchor_refs"), Mapping)
            else {}
        )
        seed_id = str(anchor_refs.get("seed_id") or record.get("provenance", {}).get("seed_id") or "").strip()
        review_item_candidates: list[GWBTargetingCandidate] = []
        for review_item in review_items_by_seed.get(seed_id, []):
            target_identity = build_review_item_target_proposition_identity(
                seed_id=seed_id,
                review_item_id=str(review_item.get("review_item_id") or "").strip(),
                lane=str(record.get("lane") or ""),
                family_id=str(record.get("family_id") or ""),
                cohort_id=str(record.get("cohort_id") or ""),
                root_artifact_id=str(record.get("root_artifact_id") or ""),
                source_family=str(record.get("source_family") or ""),
            )
            if not isinstance(target_identity, Mapping) or not target_identity:
                continue
            review_item_candidates.append(
                GWBTargetingCandidate(
                    seed_id=seed_id,
                    review_item_id=str(review_item.get("review_item_id") or "").strip(),
                    candidate_ref=str(review_item.get("review_item_id") or "").strip(),
                    candidate_kind="review_item_target",
                    relation_kind=relation_kind,
                    selection_basis="seed_linkage",
                    target_proposition_identity=dict(target_identity),
                    anchor_refs={
                        "claim_id": str(record.get("claim_id") or ""),
                        "seed_id": seed_id,
                        "review_item_id": str(review_item.get("review_item_id") or "").strip(),
                    },
                    target_split_kind=(
                        "matched_event"
                        if str(review_item.get("event_id") or "").strip()
                        else "matched_source_family"
                        if str(review_item.get("source_family") or "").strip()
                        else None
                    ),
                    target_split_value=(
                        str(review_item.get("event_id") or "").strip()
                        or str(review_item.get("source_family") or "").strip()
                        or None
                    ),
                    target_text_or_label=(
                        str(review_item.get("event_id") or "").strip()
                        or str(review_item.get("source_family") or "").strip()
                        or None
                    ),
                    target_coverage_basis=(
                        "matched_event"
                        if str(review_item.get("event_id") or "").strip()
                        else "matched_source_family"
                        if str(review_item.get("source_family") or "").strip()
                        else None
                    ),
                )
            )
        targeting_results.append(
            build_gwb_targeting_result(
                claim_id=str(record.get("claim_id") or ""),
                seed_id=seed_id,
                candidate_targets=review_item_candidates,
            )
        )
    return targeting_results


def build_review_claim_records_from_review_rows(
    *,
    rows: Sequence[Mapping[str, Any]],
    lane: str,
    family_id: str,
    cohort_id: str,
    root_artifact_id: str,
    source_family: str,
    recommended_view: str,
    queue_family: str | None = None,
    claim_id_key: str = "source_row_id",
    eligible_statuses: Sequence[str] | None = None,
    basis_kind: str = "source_review_row",
) -> list[dict[str, Any]]:
    normalized_statuses = {
        str(value).strip()
        for value in (eligible_statuses or ("missing_review", "review_required"))
        if str(value).strip()
    }
    route_family = queue_family or recommended_view or "review_queue"
    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        review_status = str(row.get("review_status") or "").strip()
        if normalized_statuses and review_status not in normalized_statuses:
            continue
        claim_id = str(row.get(claim_id_key) or "").strip()
        if not claim_id:
            continue
        proposition_identity = build_proposition_identity_dict(
            proposition_id=claim_id,
            family_id=family_id,
            cohort_id=cohort_id,
            root_artifact_id=root_artifact_id,
            lane=lane,
            source_family=source_family,
            basis_kind=basis_kind,
            local_id=claim_id,
            source_kind=str(row.get("source_kind") or "").strip(),
            upstream_artifact_ids=[
                value
                for value in (root_artifact_id, cohort_id)
                if isinstance(value, str) and value.strip()
            ],
            anchor_refs={
                "source_row_id": claim_id,
                "seed_id": str(row.get("seed_id") or "").strip(),
            },
        )
        records.append(
            build_review_claim_record_dict(
                claim_id=claim_id,
                candidate_id=claim_id,
                family_id=family_id,
                cohort_id=cohort_id,
                root_artifact_id=root_artifact_id,
                lane=lane,
                source_family=source_family,
                state="review_claim",
                state_basis="source_review_row",
                evidence_status="review_only",
                proposition_identity=proposition_identity,
                review_candidate=_build_review_candidate_for_review_row(
                    row=row,
                    claim_id=claim_id,
                    basis_kind=basis_kind,
                    review_status=review_status,
                ),
                provenance={
                    "source_kind": str(row.get("source_kind") or "").strip(),
                    "root_artifact_id": root_artifact_id,
                    "source_row_id": claim_id,
                    "source_family": str(row.get("source_family") or "").strip(),
                    "seed_id": str(row.get("seed_id") or "").strip(),
                    "upstream_artifact_ids": [
                        value
                        for value in (root_artifact_id, cohort_id)
                        if isinstance(value, str) and value.strip()
                    ],
                },
                decision_basis={
                    "basis_kind": basis_kind,
                    "review_status": review_status,
                    "primary_workload_class": str(row.get("primary_workload_class") or "").strip(),
                    "workload_classes": [
                        str(value)
                        for value in row.get("workload_classes", [])
                        if isinstance(value, str) and str(value).strip()
                    ],
                    "support_kinds": [
                        str(value)
                        for value in row.get("support_kinds", [])
                        if isinstance(value, str) and str(value).strip()
                    ],
                    "linkage_kind": str(row.get("linkage_kind") or "").strip(),
                },
                review_route={
                    "actionability": "must_review",
                    "queue_family": route_family,
                    "recommended_view": recommended_view,
                },
                review_text=_build_review_text(
                    text=row.get("text"),
                    text_role="review_source_text",
                    source_kind=str(row.get("source_kind") or "source_review_row").strip() or "source_review_row",
                    anchor_refs={
                        "source_row_id": claim_id,
                        "seed_id": str(row.get("seed_id") or "").strip(),
                    },
                    text_ref=_build_text_ref(row),
                ),
            )
        )
    return records


def build_review_claim_records_from_queue_rows(
    *,
    rows: Sequence[Mapping[str, Any]],
    lane: str,
    family_id: str,
    cohort_id: str,
    root_artifact_id: str,
    source_family: str,
    recommended_view: str,
    queue_family: str | None = None,
    claim_id_key: str = "fact_id",
    state_basis: str = "review_bundle",
    basis_kind: str = "review_queue_row",
    include_target_proposition_identity: bool = False,
    include_proposition_relation: bool = False,
) -> list[dict[str, Any]]:
    route_family = queue_family or recommended_view or "review_queue"
    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        claim_id = str(row.get(claim_id_key) or "").strip()
        if not claim_id:
            continue
        proposition_identity = build_proposition_identity_dict(
            proposition_id=claim_id,
            family_id=family_id,
            cohort_id=cohort_id,
            root_artifact_id=root_artifact_id,
            lane=lane,
            source_family=source_family,
            basis_kind=basis_kind,
            local_id=claim_id,
            source_kind="review_bundle",
            upstream_artifact_ids=[
                value
                for value in (root_artifact_id, cohort_id)
                if isinstance(value, str) and value.strip()
            ],
            anchor_refs={
                "fact_id": claim_id,
                "event_ids": [
                    str(value)
                    for value in row.get("event_ids", [])
                    if isinstance(value, str) and str(value).strip()
                ],
                "source_ids": [
                    str(value)
                    for value in row.get("source_ids", [])
                    if isinstance(value, str) and str(value).strip()
                ],
                "statement_ids": [
                    str(value)
                    for value in row.get("statement_ids", [])
                    if isinstance(value, str) and str(value).strip()
                ],
            },
        )
        target_proposition_identity = (
            build_review_queue_target_proposition_identity(
                row=row,
                lane=lane,
                family_id=family_id,
                cohort_id=cohort_id,
                root_artifact_id=root_artifact_id,
                source_family=source_family,
            )
            if include_target_proposition_identity
            else None
        )
        proposition_relation = (
            build_review_queue_proposition_relation(
                row=row,
                claim_id=claim_id,
                lane=lane,
                family_id=family_id,
                cohort_id=cohort_id,
                root_artifact_id=root_artifact_id,
                source_family=source_family,
            )
            if include_proposition_relation
            else None
        )
        records.append(
            build_review_claim_record_dict(
                claim_id=claim_id,
                candidate_id=claim_id,
                family_id=family_id,
                cohort_id=cohort_id,
                root_artifact_id=root_artifact_id,
                lane=lane,
                source_family=source_family,
                state="review_claim",
                state_basis=state_basis,
                evidence_status="review_only",
                proposition_identity=proposition_identity,
                review_candidate=_build_review_candidate(
                    candidate_id=claim_id,
                    candidate_kind="review_queue_row",
                    source_kind="review_bundle",
                    selection_basis={
                        "basis_kind": basis_kind,
                        "candidate_status": str(row.get("candidate_status") or "").strip(),
                        "latest_review_status": str(row.get("latest_review_status") or "").strip(),
                    },
                    anchor_refs={
                        "fact_id": claim_id,
                        "event_ids": [
                            str(value)
                            for value in row.get("event_ids", [])
                            if isinstance(value, str) and str(value).strip()
                        ],
                        "statement_ids": [
                            str(value)
                            for value in row.get("statement_ids", [])
                            if isinstance(value, str) and str(value).strip()
                        ],
                    },
                    target_proposition_id=(
                        str(target_proposition_identity.get("proposition_id") or "").strip()
                        if isinstance(target_proposition_identity, Mapping)
                        else None
                    ),
                ),
                target_proposition_identity=target_proposition_identity,
                proposition_relation=proposition_relation,
                review_text=_build_review_text(
                    text=row.get("label"),
                    text_role="claim_display_label",
                    source_kind="review_bundle",
                    anchor_refs={
                        "fact_id": claim_id,
                        "event_ids": [
                            str(value)
                            for value in row.get("event_ids", [])
                            if isinstance(value, str) and str(value).strip()
                        ],
                        "statement_ids": [
                            str(value)
                            for value in row.get("statement_ids", [])
                            if isinstance(value, str) and str(value).strip()
                        ],
                    },
                    text_ref=_build_text_ref(row),
                ),
                provenance={
                    "source_kind": "review_bundle",
                    "run_id": root_artifact_id,
                    "semantic_run_id": cohort_id,
                    "upstream_artifact_ids": [
                        value
                        for value in (root_artifact_id, cohort_id)
                        if isinstance(value, str) and value.strip()
                    ],
                    "event_ids": [
                        str(value)
                        for value in row.get("event_ids", [])
                        if isinstance(value, str) and str(value).strip()
                    ],
                    "source_ids": [
                        str(value)
                        for value in row.get("source_ids", [])
                        if isinstance(value, str) and str(value).strip()
                    ],
                    "statement_ids": [
                        str(value)
                        for value in row.get("statement_ids", [])
                        if isinstance(value, str) and str(value).strip()
                    ],
                },
                decision_basis={
                    "basis_kind": basis_kind,
                    "reason_codes": [
                        str(value)
                        for value in row.get("reason_codes", [])
                        if isinstance(value, str) and str(value).strip()
                    ],
                    "policy_outcomes": [
                        str(value)
                        for value in row.get("policy_outcomes", [])
                        if isinstance(value, str) and str(value).strip()
                    ],
                    "candidate_status": str(row.get("candidate_status") or "").strip(),
                    "latest_review_status": str(row.get("latest_review_status") or "").strip(),
                },
                review_route={
                    "actionability": "must_review",
                    "queue_family": route_family,
                    "recommended_view": recommended_view,
                },
            )
        )
    return records


def build_review_claim_records_from_affidavit_rows(
    *,
    rows: Sequence[Mapping[str, Any]],
    lane: str,
    family_id: str,
    cohort_id: str,
    root_artifact_id: str,
    source_family: str,
    recommended_view: str,
    queue_family: str | None = None,
    claim_id_key: str = "proposition_id",
    state_basis: str = "coverage_review_row",
    basis_kind: str = "affidavit_proposition_row",
    include_target_proposition_identity: bool = False,
    include_proposition_relation: bool = False,
) -> list[dict[str, Any]]:
    route_family = queue_family or recommended_view or "review_queue"
    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        claim_id = str(row.get(claim_id_key) or "").strip()
        if not claim_id:
            continue
        proposition_identity = build_proposition_identity_dict(
            proposition_id=claim_id,
            family_id=family_id,
            cohort_id=cohort_id,
            root_artifact_id=root_artifact_id,
            lane=lane,
            source_family=source_family,
            basis_kind=basis_kind,
            local_id=claim_id,
            source_kind="affidavit_row",
            upstream_artifact_ids=[
                value
                for value in (root_artifact_id, cohort_id)
                if isinstance(value, str) and value.strip()
            ],
            anchor_refs={
                "proposition_id": claim_id,
                "paragraph_id": str(row.get("paragraph_id") or "").strip(),
                "best_source_row_id": str(row.get("best_source_row_id") or "").strip(),
            },
        )
        target_proposition_identity = (
            build_affidavit_target_proposition_identity(
                row=row,
                lane=lane,
                family_id=family_id,
                cohort_id=cohort_id,
                root_artifact_id=root_artifact_id,
                source_family=source_family,
            )
            if include_target_proposition_identity
            else None
        )
        proposition_relation = (
            build_affidavit_proposition_relation(
                row=row,
                lane=lane,
                family_id=family_id,
                cohort_id=cohort_id,
                root_artifact_id=root_artifact_id,
                source_family=source_family,
            )
            if include_proposition_relation
            else None
        )
        records.append(
            build_review_claim_record_dict(
                claim_id=claim_id,
                candidate_id=claim_id,
                family_id=family_id,
                cohort_id=cohort_id,
                root_artifact_id=root_artifact_id,
                lane=lane,
                source_family=source_family,
                state="review_claim",
                state_basis=state_basis,
                evidence_status="review_only",
                proposition_identity=proposition_identity,
                review_candidate=_build_review_candidate(
                    candidate_id=claim_id,
                    candidate_kind="affidavit_proposition_row",
                    source_kind="affidavit_row",
                    selection_basis={
                        "basis_kind": basis_kind,
                        "coverage_status": str(row.get("coverage_status") or "").strip(),
                        "best_match_basis": str(row.get("best_match_basis") or "").strip(),
                        "best_response_role": str(row.get("best_response_role") or "").strip(),
                    },
                    anchor_refs={
                        "proposition_id": claim_id,
                        "paragraph_id": str(row.get("paragraph_id") or "").strip(),
                        "best_source_row_id": str(row.get("best_source_row_id") or "").strip(),
                    },
                    target_proposition_id=(
                        str(target_proposition_identity.get("proposition_id") or "").strip()
                        if isinstance(target_proposition_identity, Mapping)
                        else None
                    ),
                ),
                target_proposition_identity=target_proposition_identity,
                proposition_relation=proposition_relation,
                review_text=_build_review_text(
                    text=row.get("text"),
                    text_role="claim_text",
                    source_kind="affidavit_row",
                    anchor_refs={
                        "proposition_id": claim_id,
                        "paragraph_id": str(row.get("paragraph_id") or "").strip(),
                        "best_source_row_id": str(row.get("best_source_row_id") or "").strip(),
                    },
                    text_ref=_build_text_ref(row),
                ),
                provenance={
                    "source_kind": "affidavit_row",
                    "root_artifact_id": root_artifact_id,
                    "cohort_id": cohort_id,
                    "paragraph_id": str(row.get("paragraph_id") or "").strip(),
                    "paragraph_order": row.get("paragraph_order"),
                    "sentence_order": row.get("sentence_order"),
                    "best_source_row_id": str(row.get("best_source_row_id") or "").strip(),
                    "upstream_artifact_ids": [
                        value
                        for value in (root_artifact_id, cohort_id)
                        if isinstance(value, str) and value.strip()
                    ],
                },
                decision_basis={
                    "basis_kind": basis_kind,
                    "coverage_status": str(row.get("coverage_status") or "").strip(),
                    "best_match_basis": str(row.get("best_match_basis") or "").strip(),
                    "best_response_role": str(row.get("best_response_role") or "").strip(),
                },
                review_route={
                    "actionability": "must_review",
                    "queue_family": route_family,
                    "recommended_view": recommended_view,
                },
            )
        )
    return records
