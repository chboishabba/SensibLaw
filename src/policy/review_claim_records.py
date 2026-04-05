from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.models.proposition_identity import build_proposition_identity_dict
from src.models.proposition_relation import build_proposition_relation_dict
from src.models.review_claim_record import build_review_claim_record_dict


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
    review_item_by_seed: dict[str, Mapping[str, Any]] = {}
    for row in review_item_rows:
        if not isinstance(row, Mapping):
            continue
        seed_id = str(row.get("seed_id") or "").strip()
        review_item_id = str(row.get("review_item_id") or "").strip()
        if seed_id and review_item_id:
            review_item_by_seed[seed_id] = row

    attached_records: list[dict[str, Any]] = []
    for record in review_claim_records:
        copied = dict(record)
        if copied.get("target_proposition_identity") or copied.get("proposition_relation"):
            attached_records.append(copied)
            continue
        proposition_identity = (
            copied.get("proposition_identity")
            if isinstance(copied.get("proposition_identity"), Mapping)
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
        seed_id = str(anchor_refs.get("seed_id") or copied.get("provenance", {}).get("seed_id") or "").strip()
        review_item = review_item_by_seed.get(seed_id)
        if not seed_id or not isinstance(review_item, Mapping):
            attached_records.append(copied)
            continue
        target_identity = build_review_item_target_proposition_identity(
            seed_id=seed_id,
            review_item_id=str(review_item.get("review_item_id") or "").strip(),
            lane=str(copied.get("lane") or ""),
            family_id=str(copied.get("family_id") or ""),
            cohort_id=str(copied.get("cohort_id") or ""),
            root_artifact_id=str(copied.get("root_artifact_id") or ""),
            source_family=str(copied.get("source_family") or ""),
        )
        if not isinstance(target_identity, Mapping) or not target_identity:
            attached_records.append(copied)
            continue
        copied["target_proposition_identity"] = dict(target_identity)
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
                "review_item_id": str(review_item.get("review_item_id") or "").strip(),
            },
        )
        attached_records.append(copied)
    return attached_records


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
                target_proposition_identity=target_proposition_identity,
                proposition_relation=proposition_relation,
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
                target_proposition_identity=target_proposition_identity,
                proposition_relation=proposition_relation,
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
