from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from src.models.action_policy import ACTION_POLICY_SCHEMA_VERSION, build_action_policy_record
from src.models.convergence import CONVERGENCE_SCHEMA_VERSION, build_convergence_record
from src.models.conflict import CONFLICT_SCHEMA_VERSION, build_conflict_set
from src.models.nat_claim import NAT_CLAIM_SCHEMA_VERSION, build_nat_claim_dict
from src.models.temporal import TEMPORAL_SCHEMA_VERSION, build_temporal_envelope
from src.policy.world_model import build_state_node

AdapterValue = str | int | float | bool | Mapping[str, Any] | Sequence[Any] | None
RowContextExtractor = str | Callable[[Mapping[str, Any], Mapping[str, Any]], AdapterValue]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [deepcopy(dict(row)) for row in value if isinstance(row, Mapping)]


def _extract(
    spec: RowContextExtractor,
    row: Mapping[str, Any],
    context: Mapping[str, Any],
) -> AdapterValue:
    if callable(spec):
        return spec(row, context)
    return row.get(spec)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_text(item) for item in value if _text(item)]


def _deepcopy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return deepcopy(dict(value))


def copy_artifact_fields(artifact: Mapping[str, Any], *field_names: str) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for field_name in field_names:
        value = artifact.get(field_name)
        if isinstance(value, Mapping):
            copied[field_name] = deepcopy(dict(value))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            copied[field_name] = [deepcopy(dict(row)) if isinstance(row, Mapping) else row for row in value]
        else:
            copied[field_name] = value
    return copied


def build_authority_surface_rows(surface_ids: Sequence[str]) -> list[dict[str, Any]]:
    return [{"surface_id": _text(value), "status": "reviewed"} for value in surface_ids if _text(value)]


def build_record_rows_from_mapping(
    rows: Sequence[Mapping[str, Any]],
    *,
    field_mapping: Mapping[str, RowContextExtractor],
    context: Mapping[str, Any] | None = None,
    predicate: Callable[[Mapping[str, Any], Mapping[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    normalized_context = dict(context or {})
    built: list[dict[str, Any]] = []
    for row in rows:
        if predicate is not None and not predicate(row, normalized_context):
            continue
        payload: dict[str, Any] = {}
        for field_name, spec in field_mapping.items():
            value = _extract(spec, row, normalized_context)
            if value is None:
                continue
            payload[field_name] = deepcopy(value)
        if payload:
            built.append(payload)
    return built


def build_event_nodes_from_mapping(
    rows: Sequence[Mapping[str, Any]],
    *,
    field_mapping: Mapping[str, RowContextExtractor],
    context: Mapping[str, Any] | None = None,
    predicate: Callable[[Mapping[str, Any], Mapping[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    return build_record_rows_from_mapping(rows, field_mapping=field_mapping, context=context, predicate=predicate)


def build_timeline_nodes_from_mapping(
    rows: Sequence[Mapping[str, Any]],
    *,
    field_mapping: Mapping[str, RowContextExtractor],
    context: Mapping[str, Any] | None = None,
    predicate: Callable[[Mapping[str, Any], Mapping[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    return build_record_rows_from_mapping(rows, field_mapping=field_mapping, context=context, predicate=predicate)


@dataclass(frozen=True)
class StateNodeMapping:
    node_id: RowContextExtractor
    node_kind: RowContextExtractor
    label: RowContextExtractor
    status: RowContextExtractor = "status"
    source_anchor_ids: RowContextExtractor | None = None
    authority_surface: RowContextExtractor | None = None
    promotion_status: RowContextExtractor | None = None
    conflict_ids: RowContextExtractor | None = None
    residual: RowContextExtractor | None = None
    metadata: RowContextExtractor | None = None


def build_claim_nodes_from_mapping(
    rows: Sequence[Mapping[str, Any]],
    *,
    mapping: StateNodeMapping,
    context: Mapping[str, Any] | None = None,
    predicate: Callable[[Mapping[str, Any], Mapping[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    normalized_context = dict(context or {})
    built: list[dict[str, Any]] = []
    for row in rows:
        if predicate is not None and not predicate(row, normalized_context):
            continue
        node_id = _text(_extract(mapping.node_id, row, normalized_context))
        if not node_id:
            continue
        built.append(
            build_state_node(
                node_id=node_id,
                node_kind=_text(_extract(mapping.node_kind, row, normalized_context)),
                label=_text(_extract(mapping.label, row, normalized_context)),
                status=_text(_extract(mapping.status, row, normalized_context)) or "candidate",
                source_anchor_ids=_string_list(
                    _extract(mapping.source_anchor_ids, row, normalized_context) if mapping.source_anchor_ids else []
                ),
                authority_surface=_text(
                    _extract(mapping.authority_surface, row, normalized_context) if mapping.authority_surface else ""
                )
                or None,
                promotion_status=_text(
                    _extract(mapping.promotion_status, row, normalized_context) if mapping.promotion_status else ""
                )
                or None,
                conflict_ids=_string_list(
                    _extract(mapping.conflict_ids, row, normalized_context) if mapping.conflict_ids else []
                ),
                residual=_deepcopy_mapping(
                    _extract(mapping.residual, row, normalized_context) if mapping.residual else {}
                )
                or None,
                metadata=_deepcopy_mapping(
                    _extract(mapping.metadata, row, normalized_context) if mapping.metadata else {}
                ),
            )
        )
    return built


@dataclass(frozen=True)
class ReviewClaimRecordMapping:
    claim_id: RowContextExtractor
    canonical_form: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]
    source_family: RowContextExtractor
    authority_level: RowContextExtractor
    claim_status: RowContextExtractor
    evidence_status: RowContextExtractor
    root_artifact_id: RowContextExtractor
    provenance_chain: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]
    source_property: RowContextExtractor
    target_property: RowContextExtractor
    state_basis: RowContextExtractor
    candidate_id: RowContextExtractor | None = None
    cohort_id: RowContextExtractor | None = None


@dataclass(frozen=True)
class ClaimStateRecordMapping:
    claim_id: RowContextExtractor
    canonical_form: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]
    source_family: RowContextExtractor
    authority_level: RowContextExtractor
    claim_status: RowContextExtractor
    evidence_status: RowContextExtractor
    root_artifact_id: RowContextExtractor
    provenance_chain: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]
    source_property: RowContextExtractor
    target_property: RowContextExtractor
    state_basis: RowContextExtractor
    nat_claim_state: RowContextExtractor
    candidate_id: RowContextExtractor | None = None
    cohort_id: RowContextExtractor | None = None
    source_unit_id: RowContextExtractor | None = None
    run_id: RowContextExtractor | None = None
    evidence_row: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]] | None = None


def build_review_inputs(
    artifact: Mapping[str, Any],
    *,
    extra_fields: Mapping[str, Any] | None = None,
    field_names: Sequence[str] = (),
) -> dict[str, Any]:
    payload = copy_artifact_fields(artifact, *field_names)
    payload.update(deepcopy(dict(extra_fields or {})))
    return payload


def build_review_claim_records(
    rows: Sequence[Mapping[str, Any]],
    *,
    family_id: str,
    mapping: ReviewClaimRecordMapping,
    context: Mapping[str, Any] | None = None,
    predicate: Callable[[Mapping[str, Any], Mapping[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    normalized_context = dict(context or {})
    claims: list[dict[str, Any]] = []
    for row in rows:
        if predicate is not None and not predicate(row, normalized_context):
            continue
        claim_id = _text(_extract(mapping.claim_id, row, normalized_context))
        if not claim_id:
            continue
        candidate_id = _text(_extract(mapping.candidate_id or mapping.claim_id, row, normalized_context)) or claim_id
        cohort_id = _text(_extract(mapping.cohort_id or mapping.root_artifact_id, row, normalized_context))
        root_artifact_id = _text(_extract(mapping.root_artifact_id, row, normalized_context))
        canonical_form = deepcopy(dict(mapping.canonical_form(row, normalized_context)))
        source_family = _text(_extract(mapping.source_family, row, normalized_context))
        authority_level = _text(_extract(mapping.authority_level, row, normalized_context))
        claim_status = _text(_extract(mapping.claim_status, row, normalized_context)) or "REVIEW_ONLY"
        evidence_status = _text(_extract(mapping.evidence_status, row, normalized_context)) or "review_only"
        provenance_chain = deepcopy(dict(mapping.provenance_chain(row, normalized_context)))
        evidence_paths = [
            {
                "evidence_path_id": f"{claim_id}:{root_artifact_id}",
                "run_id": root_artifact_id,
                "root_artifact_id": root_artifact_id,
                "source_unit_id": claim_id,
                "source_family": source_family,
                "authority_level": authority_level,
                "verification_status": evidence_status,
                "provenance_chain": provenance_chain,
            }
        ]
        claim = {
            "claim_id": claim_id,
            "candidate_id": candidate_id,
            "family_id": family_id,
            "cohort_id": cohort_id or root_artifact_id,
            "status": claim_status,
            "canonical_form": canonical_form,
            "evidence_paths": evidence_paths,
            "independent_root_artifact_ids": [root_artifact_id] if root_artifact_id else [],
            "evidence_count": len(evidence_paths),
        }
        claim["nat_claim"] = build_nat_claim_dict(
            claim_id=claim_id,
            family_id=family_id,
            cohort_id=cohort_id or root_artifact_id,
            candidate_id=candidate_id,
            canonical_form=canonical_form,
            source_property=_text(_extract(mapping.source_property, row, normalized_context)),
            target_property=_text(_extract(mapping.target_property, row, normalized_context)),
            state="review_claim",
            state_basis=_text(_extract(mapping.state_basis, row, normalized_context)),
            root_artifact_id=root_artifact_id,
            provenance={"source_family": source_family, **provenance_chain},
            evidence_status=evidence_status,
        )
        claim["convergence"] = build_convergence_record(
            claim_id=claim_id,
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=claim["independent_root_artifact_ids"],
            claim_status=claim_status,
        )
        claim["temporal"] = build_temporal_envelope(
            claim_id=claim_id,
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=claim["independent_root_artifact_ids"],
        )
        claim["conflict_set"] = build_conflict_set(
            claim_id=claim_id,
            candidate_ids=[candidate_id],
            evidence_rows=[
                {
                    "run_id": root_artifact_id,
                    "root_artifact_id": root_artifact_id,
                    "canonical_form": canonical_form,
                }
            ],
        )
        claim["action_policy"] = build_action_policy_record(
            claim_id=claim_id,
            claim_status=claim_status,
            convergence=claim["convergence"],
            temporal=claim["temporal"],
            conflict_set=claim["conflict_set"],
        )
        claims.append(claim)
    return claims


def build_claim_state_records(
    rows: Sequence[Mapping[str, Any]],
    *,
    family_id: str,
    mapping: ClaimStateRecordMapping,
    context: Mapping[str, Any] | None = None,
    predicate: Callable[[Mapping[str, Any], Mapping[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    normalized_context = dict(context or {})
    claims: list[dict[str, Any]] = []
    for row in rows:
        if predicate is not None and not predicate(row, normalized_context):
            continue
        claim_id = _text(_extract(mapping.claim_id, row, normalized_context))
        if not claim_id:
            continue
        candidate_id = _text(_extract(mapping.candidate_id or mapping.claim_id, row, normalized_context)) or claim_id
        cohort_id = _text(_extract(mapping.cohort_id or mapping.root_artifact_id, row, normalized_context))
        root_artifact_id = _text(_extract(mapping.root_artifact_id, row, normalized_context))
        source_unit_id = _text(_extract(mapping.source_unit_id or mapping.claim_id, row, normalized_context)) or claim_id
        run_id = _text(_extract(mapping.run_id or mapping.root_artifact_id, row, normalized_context)) or root_artifact_id
        canonical_form = deepcopy(dict(mapping.canonical_form(row, normalized_context)))
        source_family = _text(_extract(mapping.source_family, row, normalized_context))
        authority_level = _text(_extract(mapping.authority_level, row, normalized_context))
        claim_status = _text(_extract(mapping.claim_status, row, normalized_context)) or "REVIEW_ONLY"
        evidence_status = _text(_extract(mapping.evidence_status, row, normalized_context)) or "review_only"
        nat_claim_state = _text(_extract(mapping.nat_claim_state, row, normalized_context)) or claim_status
        provenance_chain = deepcopy(dict(mapping.provenance_chain(row, normalized_context)))
        evidence_path = {
            "evidence_path_id": f"{claim_id}:{root_artifact_id}",
            "run_id": run_id,
            "root_artifact_id": root_artifact_id,
            "source_unit_id": source_unit_id,
            "source_family": source_family,
            "authority_level": authority_level,
            "verification_status": evidence_status,
            "provenance_chain": provenance_chain,
        }
        evidence_paths = [evidence_path]
        claim = {
            "claim_id": claim_id,
            "candidate_id": candidate_id,
            "family_id": family_id,
            "cohort_id": cohort_id or root_artifact_id,
            "status": claim_status,
            "canonical_form": canonical_form,
            "evidence_paths": evidence_paths,
            "independent_root_artifact_ids": [root_artifact_id] if root_artifact_id else [],
            "evidence_count": len(evidence_paths),
            "state_basis": _text(_extract(mapping.state_basis, row, normalized_context)),
        }
        claim["nat_claim"] = build_nat_claim_dict(
            claim_id=claim_id,
            family_id=family_id,
            cohort_id=cohort_id or root_artifact_id,
            candidate_id=candidate_id,
            canonical_form=canonical_form,
            source_property=_text(_extract(mapping.source_property, row, normalized_context)),
            target_property=_text(_extract(mapping.target_property, row, normalized_context)),
            state=nat_claim_state,
            state_basis=claim["state_basis"],
            root_artifact_id=root_artifact_id,
            provenance={"source_family": source_family, **provenance_chain},
            evidence_status=evidence_status,
        )
        claim["convergence"] = build_convergence_record(
            claim_id=claim_id,
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=claim["independent_root_artifact_ids"],
            claim_status=claim_status,
        )
        claim["temporal"] = build_temporal_envelope(
            claim_id=claim_id,
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=claim["independent_root_artifact_ids"],
        )
        evidence_row = (
            deepcopy(dict(mapping.evidence_row(row, normalized_context)))
            if mapping.evidence_row is not None
            else {
                "run_id": run_id,
                "root_artifact_id": root_artifact_id,
                "canonical_form": canonical_form,
            }
        )
        claim["conflict_set"] = build_conflict_set(
            claim_id=claim_id,
            candidate_ids=[candidate_id],
            evidence_rows=[evidence_row],
        )
        claim["action_policy"] = build_action_policy_record(
            claim_id=claim_id,
            claim_status=claim_status,
            convergence=claim["convergence"],
            temporal=claim["temporal"],
            conflict_set=claim["conflict_set"],
        )
        claims.append(claim)
    return claims


__all__ = [
    "ACTION_POLICY_SCHEMA_VERSION",
    "ClaimStateRecordMapping",
    "CONVERGENCE_SCHEMA_VERSION",
    "CONFLICT_SCHEMA_VERSION",
    "NAT_CLAIM_SCHEMA_VERSION",
    "TEMPORAL_SCHEMA_VERSION",
    "ReviewClaimRecordMapping",
    "StateNodeMapping",
    "build_authority_surface_rows",
    "build_claim_nodes_from_mapping",
    "build_claim_state_records",
    "build_event_nodes_from_mapping",
    "build_record_rows_from_mapping",
    "build_review_claim_records",
    "build_review_inputs",
    "build_timeline_nodes_from_mapping",
    "copy_artifact_fields",
]
