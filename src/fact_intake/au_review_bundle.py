from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from .control_plane import build_follow_control_plane, build_follow_queue_item, summarize_follow_queue
from .payload_builder import (
    build_excerpt_row,
    build_fact_candidate_row,
    build_fact_intake_payload,
    build_fact_intake_run,
    build_source_rows,
    build_statement_row,
    ensure_event_source_row,
    sha256_payload,
)
from .read_model import build_fact_intake_report, build_fact_review_operator_views, build_fact_review_run_summary
from .review_bundle import (
    build_abstentions,
    build_bundle_workflow_summary,
    build_event_chronology,
    build_fact_review_bundle_payload,
)
from .projection_helpers import (
    build_relation_observation,
    build_role_observation,
    fact_status_for_statement,
    observation_status_from_relation,
)
from src.models.action_policy import ACTION_POLICY_SCHEMA_VERSION, build_action_policy_record
from src.models.convergence import CONVERGENCE_SCHEMA_VERSION, build_convergence_record
from src.models.conflict import CONFLICT_SCHEMA_VERSION, build_conflict_set
from src.models.nat_claim import NAT_CLAIM_SCHEMA_VERSION, build_nat_claim_dict
from src.models.review_claim_record import REVIEW_CLAIM_RECORD_SCHEMA_VERSION
from src.models.temporal import TEMPORAL_SCHEMA_VERSION, build_temporal_envelope
from src.policy.compiler_contract import build_au_fact_review_bundle_contract
from src.policy.legal_follow_graph import (
    build_au_legal_follow_graph,
    build_au_legal_follow_operator_view,
)
from src.policy.product_gate import build_product_gate
from src.policy.review_claim_records import build_review_claim_records_from_queue_rows
from src.policy.reasoner_input_artifact import build_reasoner_input_artifact
from src.policy.suite_normalized_artifact import build_au_fact_review_bundle_normalized_artifact

_ROLE_TO_PREDICATE = {
    "party_appellant": ("actor", "actor_role", "Appellant"),
    "party_respondent": ("actor", "actor_role", "Respondent"),
    "party_plaintiff": ("actor", "actor_role", "Plaintiff"),
    "party_defendant": ("actor", "actor_role", "Defendant"),
    "party_accused": ("actor", "actor_role", "Accused"),
    "party_applicant": ("actor", "actor_role", "Applicant"),
    "legal_representative": ("actor", "actor_role", "Legal Representative"),
    "office_context": ("organization", None, None),
    "forum": ("organization", "actor_role", "Forum"),
}

_LEXICAL_MODE_BY_SOURCE_TYPE = {
    "judgment_extract": "au_legal",
    "timeline_payload": "au_legal",
    "legal_record": "au_legal",
}
_AU_AUTHORITY_ROUTE_TARGET_SCORE = {
    "known_authority_fetch": ("high", 5),
    "citation_follow": ("high", 4),
    "authority_title_resolution": ("medium", 3),
    "manual_review": ("low", 1),
}
AU_FACT_REVIEW_BUNDLE_WORLD_MODEL_SCHEMA_VERSION = "sl.au_fact_review_bundle_world_model.v0_1"


def _build_au_review_claim_records(
    *,
    review_queue: Sequence[Mapping[str, Any]],
    run_id: str,
    semantic_run_id: str,
    workflow_summary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    recommended_view = str(workflow_summary.get("recommended_view") or "").strip()
    return build_review_claim_records_from_queue_rows(
        rows=review_queue,
        lane="au",
        family_id="au_fact_review_bundle",
        cohort_id=semantic_run_id,
        root_artifact_id=run_id,
        source_family="au_fact_review_bundle",
        recommended_view=recommended_view,
        queue_family=recommended_view or "review_queue",
        claim_id_key="fact_id",
        state_basis="review_bundle",
        basis_kind="review_queue_row",
        include_target_proposition_identity=True,
        include_proposition_relation=True,
    )

def _normalize_opt_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _collect_au_typing_deficit_signals(semantic_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_signals = semantic_report.get("typing_deficit_signals")
    if isinstance(raw_signals, Sequence):
        normalized: list[dict[str, Any]] = []
        for signal in raw_signals:
            if not isinstance(signal, Mapping):
                continue
            entry = dict(signal)
            entry.setdefault("source", "au")
            entry.setdefault("signal_kind", "missing_instance_of_typing_deficit")
            normalized.append(entry)
        return normalized
    qids = semantic_report.get("typing_deficit_qids")
    if isinstance(qids, Sequence):
        return [
            {
                "signal_id": f"au:{_stringify(qid)}",
                "source": "au",
                "signal_kind": "missing_instance_of_typing_deficit",
                "linked_qid": _stringify(qid),
            }
            for qid in qids
            if _stringify(qid)
        ]
    return []


def _lexical_mode(source_type: str) -> str | None:
    return _LEXICAL_MODE_BY_SOURCE_TYPE.get(str(source_type or "").strip())


def _reference_class_counts(details: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "case": 0,
        "supporting_legislation": 0,
        "supporting_instrument": 0,
        "institutional_reference": 0,
        "other": 0,
    }
    for row in details:
        reference_class = str(row.get("reference_class") or "other").strip() or "other"
        counts[reference_class] = counts.get(reference_class, 0) + 1
    return {key: value for key, value in counts.items() if value > 0}


def _detail_label_counts(details: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in details:
        label = str(row.get(key) or "").strip()
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return counts


def _detail_ref_kind_counts(details: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in details:
        label = str(row.get("ref_kind") or "").strip()
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return counts


def _citation_label_counts(details: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in details:
        label = str(row.get(key) or "").strip()
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return counts


def _citation_year_counts(details: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in details:
        value = row.get("year_hint")
        if value in {None, ""}:
            continue
        label = str(value)
        counts[label] = counts.get(label, 0) + 1
    return counts


def _authority_follow_priority(
    *,
    route_target: str,
    authority_title_count: int,
    legal_ref_count: int,
    citation_detail_count: int,
) -> tuple[int, str]:
    authority_yield, base_score = _AU_AUTHORITY_ROUTE_TARGET_SCORE.get(route_target, ("low", 1))
    score = base_score
    if authority_title_count:
        score += 1
    if legal_ref_count:
        score += 1
    if citation_detail_count:
        score += 1
    return score, authority_yield


def _build_authority_follow_operator_view(semantic_report: Mapping[str, Any]) -> dict[str, Any]:
    authority_receipts = semantic_report.get("authority_receipts")
    if not isinstance(authority_receipts, Mapping):
        return {
            "available": False,
            "control_plane": build_follow_control_plane(
                source_family="au_authority",
                hint_kind="authority_hint",
                receipt_kind="authority_ingest_receipt",
                substrate_kind="authority_substrate_summary",
                conjecture_kind="follow_needed_conjecture",
                route_targets=["authority_title_resolution", "citation_follow", "known_authority_fetch", "manual_review"],
                resolution_statuses=["open", "resolved", "reviewed"],
            ),
            "summary": {
                "authority_receipt_count": 0,
                "follow_needed_event_count": 0,
                "conjecture_count": 0,
                "route_target_counts": {},
                "resolution_status_counts": {},
            },
            "queue": [],
        }
    summary = authority_receipts.get("summary") if isinstance(authority_receipts.get("summary"), Mapping) else {}
    conjectures = [
        row
        for row in authority_receipts.get("follow_needed_conjectures", [])
        if isinstance(row, Mapping)
    ]
    queue: list[dict[str, Any]] = []
    for row in conjectures:
        route_target = str(row.get("route_target") or "manual_review")
        candidate_citations = [
            str(value)
            for value in row.get("candidate_citations", [])
            if isinstance(value, str) and str(value).strip()
        ]
        authority_titles = [
            str(value)
            for value in row.get("authority_titles", [])
            if isinstance(value, str) and str(value).strip()
        ]
        legal_refs = [
            str(value)
            for value in row.get("legal_refs", [])
            if isinstance(value, str) and str(value).strip()
        ]
        legal_ref_details = [
            value for value in row.get("legal_ref_details", []) if isinstance(value, Mapping)
        ]
        legal_ref_class_counts = _reference_class_counts(legal_ref_details)
        ref_kind_counts = _detail_ref_kind_counts(legal_ref_details)
        jurisdiction_hint_counts = _detail_label_counts(legal_ref_details, "jurisdiction_hint")
        instrument_kind_counts = _detail_label_counts(legal_ref_details, "instrument_kind")
        candidate_citation_details = [
            value for value in row.get("candidate_citation_details", []) if isinstance(value, Mapping)
        ]
        citation_court_hint_counts = _citation_label_counts(candidate_citation_details, "court_hint")
        citation_year_counts = _citation_year_counts(candidate_citation_details)
        authority_term_tokens = [
            str(value)
            for value in row.get("authority_term_tokens", [])
            if isinstance(value, str) and str(value).strip()
        ]
        priority_score, authority_yield = _authority_follow_priority(
            route_target=route_target,
            authority_title_count=len(authority_titles),
            legal_ref_count=len(legal_ref_details),
            citation_detail_count=len(candidate_citation_details),
        )
        queue.append(
            build_follow_queue_item(
                item_id=str(row.get("event_id") or ""),
                title=_normalize_opt_text(row.get("event_section")) or "Authority follow",
                subtitle=str(row.get("conjecture_kind") or ""),
                description=_normalize_opt_text(row.get("event_text")),
                conjecture_kind=str(row.get("conjecture_kind") or ""),
                route_target=route_target,
                resolution_status="open",
                chips=candidate_citations,
                detail_rows=[
                    {"label": "Resolution hint", "value": str(row.get("resolution_hint") or "")},
                    {"label": "Authority yield", "value": authority_yield},
                    {"label": "Titles", "value": ", ".join(authority_titles)},
                    {"label": "Legal refs", "value": ", ".join(legal_refs)},
                    {
                        "label": "Reference classes",
                        "value": ", ".join(f"{key}: {value}" for key, value in sorted(legal_ref_class_counts.items())) or "none",
                    },
                    {
                        "label": "Reference kinds",
                        "value": ", ".join(f"{key}: {value}" for key, value in sorted(ref_kind_counts.items())) or "none",
                    },
                    {
                        "label": "Detected citations",
                        "value": str(len(candidate_citation_details)),
                    },
                    {
                        "label": "Citation courts",
                        "value": ", ".join(f"{key}: {value}" for key, value in sorted(citation_court_hint_counts.items())) or "none",
                    },
                    {
                        "label": "Citation years",
                        "value": ", ".join(f"{key}: {value}" for key, value in sorted(citation_year_counts.items())) or "none",
                    },
                    {
                        "label": "Jurisdictions",
                        "value": ", ".join(f"{key}: {value}" for key, value in sorted(jurisdiction_hint_counts.items())) or "none",
                    },
                    {
                        "label": "Instrument kinds",
                        "value": ", ".join(f"{key}: {value}" for key, value in sorted(instrument_kind_counts.items())) or "none",
                    },
                    {"label": "Terms", "value": ", ".join(authority_term_tokens)},
                ],
                extra={
                    "event_id": str(row.get("event_id") or ""),
                    "event_section": _normalize_opt_text(row.get("event_section")),
                    "event_text": _normalize_opt_text(row.get("event_text")),
                    "resolution_hint": str(row.get("resolution_hint") or ""),
                    "priority_score": priority_score,
                    "authority_yield": authority_yield,
                    "candidate_citations": candidate_citations,
                    "candidate_citation_details": candidate_citation_details,
                    "citation_court_hint_counts": citation_court_hint_counts,
                    "citation_year_counts": citation_year_counts,
                    "authority_titles": authority_titles,
                    "legal_refs": legal_refs,
                    "legal_ref_details": legal_ref_details,
                    "legal_ref_class_counts": legal_ref_class_counts,
                    "ref_kind_counts": ref_kind_counts,
                    "jurisdiction_hint_counts": jurisdiction_hint_counts,
                    "instrument_kind_counts": instrument_kind_counts,
                    "authority_term_tokens": authority_term_tokens,
                },
            )
        )
    queue.sort(
        key=lambda row: (
            -int(row.get("priority_score") or 0),
            str(row.get("route_target") or ""),
            str(row.get("title") or ""),
        )
    )
    for index, row in enumerate(queue, start=1):
        row["priority_rank"] = index
    queue_summary = summarize_follow_queue(queue)
    priority_band_counts = {"high": 0, "medium": 0, "low": 0}
    highest_priority_score = 0
    highest_authority_yield = "low"
    for row in queue:
        authority_yield = str(row.get("authority_yield") or "low")
        if authority_yield not in priority_band_counts:
            priority_band_counts[authority_yield] = 0
        priority_band_counts[authority_yield] += 1
        score = int(row.get("priority_score") or 0)
        if score > highest_priority_score:
            highest_priority_score = score
            highest_authority_yield = authority_yield
    return {
        "available": True,
        "control_plane": build_follow_control_plane(
            source_family="au_authority",
            hint_kind="authority_hint",
            receipt_kind="authority_ingest_receipt",
            substrate_kind="authority_substrate_summary",
            conjecture_kind="follow_needed_conjecture",
            route_targets=list(queue_summary["route_target_counts"].keys()),
            resolution_statuses=list(queue_summary["resolution_status_counts"].keys()),
        ),
        "summary": {
            "authority_receipt_count": int(summary.get("authority_receipt_count") or 0),
            "follow_needed_event_count": int(summary.get("follow_needed_event_count") or 0),
            "conjecture_count": int(summary.get("conjecture_count") or 0),
            "legal_ref_class_counts": dict(summary.get("legal_ref_class_counts", {}))
            if isinstance(summary.get("legal_ref_class_counts"), Mapping)
            else {},
            "ref_kind_counts": dict(summary.get("ref_kind_counts", {}))
            if isinstance(summary.get("ref_kind_counts"), Mapping)
            else {},
            "citation_court_hint_counts": dict(summary.get("citation_court_hint_counts", {}))
            if isinstance(summary.get("citation_court_hint_counts"), Mapping)
            else {},
            "citation_year_counts": dict(summary.get("citation_year_counts", {}))
            if isinstance(summary.get("citation_year_counts"), Mapping)
            else {},
            "jurisdiction_hint_counts": dict(summary.get("jurisdiction_hint_counts", {}))
            if isinstance(summary.get("jurisdiction_hint_counts"), Mapping)
            else {},
                "instrument_kind_counts": dict(summary.get("instrument_kind_counts", {}))
                if isinstance(summary.get("instrument_kind_counts"), Mapping)
                else {},
                "route_target_counts": queue_summary["route_target_counts"],
                "resolution_status_counts": queue_summary["resolution_status_counts"],
                "queue_count": queue_summary["queue_count"],
                "priority_band_counts": priority_band_counts,
                "highest_priority_score": highest_priority_score,
                "highest_authority_yield": highest_authority_yield,
        },
        "queue": queue,
    }


def build_fact_intake_payload_from_au_semantic_report(
    report: Mapping[str, Any],
    *,
    timeline_events: list[Mapping[str, Any]] | None = None,
    source_label: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    semantic_run_id = str(report.get("run_id") or "").strip()
    if not semantic_run_id:
        raise ValueError("AU semantic report run_id is required")
    per_event = timeline_events if timeline_events is not None else (
        list(report.get("per_event", [])) if isinstance(report.get("per_event"), list) else []
    )
    report_relation_candidates = list(report.get("relation_candidates", [])) if isinstance(report.get("relation_candidates"), list) else []
    relation_candidates_by_event: dict[str, list[Mapping[str, Any]]] = {}
    for row in report_relation_candidates:
        if isinstance(row, Mapping):
            relation_candidates_by_event.setdefault(str(row.get("event_id") or ""), []).append(row)
    source_documents = list(report.get("source_documents", [])) if isinstance(report.get("source_documents"), list) else []
    run = build_fact_intake_run(
        run_kind="au_fact_intake_run",
        semantic_run_id=semantic_run_id,
        per_event=per_event,
        source_documents=source_documents,
        source_label=source_label or f"au_semantic:{semantic_run_id}",
        notes=notes or f"Derived from AU semantic run {semantic_run_id}",
    )
    run_id = str(run["run_id"])

    event_source_document_map: dict[str, str] = {}
    for document in source_documents:
        source_document_id = str(document.get("sourceDocumentId") or "").strip()
        for event_id in document.get("eventIds", []) if isinstance(document.get("eventIds"), list) else []:
            event_source_document_map[str(event_id)] = source_document_id

    sources, source_map = build_source_rows(
        run_id=run_id,
        semantic_run_id=semantic_run_id,
        source_documents=source_documents,
        default_source_type="timeline_payload",
        lexical_mode_for=_lexical_mode,
    )

    excerpts: list[dict[str, Any]] = []
    statements: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    fact_candidates: list[dict[str, Any]] = []

    for index, event in enumerate(per_event, start=1):
        event_id = str(event.get("event_id") or "").strip()
        source_document_id = str(
            event.get("source_document_id")
            or event.get("source_id")
            or event_source_document_map.get(event_id)
            or ""
        ).strip()
        source_id = ensure_event_source_row(
            sources=sources,
            source_map=source_map,
            run_id=run_id,
            semantic_run_id=semantic_run_id,
            source_document_id=source_document_id,
            source_type=str(event.get("source_type") or "timeline_payload"),
            source_text=str(event.get("text") or ""),
            lexical_mode_for=_lexical_mode,
            source_document_value=source_document_id or None,
        )
        statement_observations: list[dict[str, Any]] = []

        section = _normalize_opt_text(event.get("section"))
        excerpt = build_excerpt_row(
            run_id=run_id,
            semantic_run_id=semantic_run_id,
            event_id=event_id,
            source_id=source_id,
            excerpt_order=index,
            excerpt_text=str(event.get("text") or ""),
            char_start=event.get("source_char_start"),
            char_end=event.get("source_char_end"),
            anchor_label=event_id,
            extra_provenance={"section": section} if section else None,
        )
        chronology_hint = _normalize_opt_text((event.get("anchor") or {}).get("text") if isinstance(event.get("anchor"), Mapping) else None)
        statement = build_statement_row(
            run_id=run_id,
            semantic_run_id=semantic_run_id,
            event_id=event_id,
            excerpt_id=str(excerpt["excerpt_id"]),
            statement_text=str(event.get("text") or ""),
            statement_role="au_timeline_statement",
            chronology_hint=chronology_hint,
            extra_provenance={"section": section} if section else None,
        )
        excerpt_id = str(excerpt["excerpt_id"])
        statement_id = str(statement["statement_id"])
        excerpts.append(excerpt)
        statements.append(statement)

        anchor = event.get("anchor") if isinstance(event.get("anchor"), Mapping) else {}
        anchor_text = _normalize_opt_text(anchor.get("text")) or _normalize_opt_text(anchor.get("year"))
        if anchor_text:
            statement_observations.append(
                build_relation_observation(
                    run_id=run_id,
                    event_id=event_id,
                    kind="anchor",
                    statement_id=statement_id,
                    excerpt_id=excerpt_id,
                    source_id=source_id,
                    observation_order=len(statement_observations) + 1,
                    relation_index=0,
                    predicate_key="event_date",
                    predicate_family="temporal",
                    object_text=anchor_text,
                    object_type="date_hint",
                    object_ref=None,
                    subject_text=_normalize_opt_text(event.get("section")),
                    observation_status="captured",
                    semantic_run_id=semantic_run_id,
                    relation_candidate_id=None,
                    source_predicate_key="event_date",
                    promotion_status="captured",
                    extra_provenance={"anchor_kind": "timeline_anchor"},
                )
            )

        for role_index, role in enumerate(event.get("event_roles", []), start=1):
            if not isinstance(role, Mapping):
                continue
            role_kind = str(role.get("role_kind") or "").strip()
            mapping = _ROLE_TO_PREDICATE.get(role_kind)
            entity = role.get("entity") if isinstance(role.get("entity"), Mapping) else {}
            object_text = str(entity.get("canonical_label") or entity.get("canonical_key") or "").strip()
            if mapping is None or not object_text:
                continue
            primary_predicate, secondary_predicate, secondary_label = mapping
            statement_observations.append(
                build_role_observation(
                    run_id=run_id,
                    event_id=event_id,
                    statement_id=statement_id,
                    excerpt_id=excerpt_id,
                    source_id=source_id,
                    observation_order=len(statement_observations) + 1,
                    role_index=role_index,
                    predicate_key=primary_predicate,
                    predicate_family="actor_identification",
                    object_text=object_text,
                    object_type=str(entity.get("entity_kind") or "semantic_entity"),
                    object_ref=_normalize_opt_text(entity.get("canonical_key")),
                    subject_text=None,
                    observation_status="captured",
                    semantic_run_id=semantic_run_id,
                    role_kind=role_kind,
                )
            )
            if secondary_predicate and secondary_label:
                statement_observations.append(
                    build_role_observation(
                        run_id=run_id,
                        event_id=event_id,
                        statement_id=statement_id,
                        excerpt_id=excerpt_id,
                        source_id=source_id,
                        observation_order=len(statement_observations) + 1,
                        role_index=role_index,
                        predicate_key=secondary_predicate,
                        predicate_family="actor_identification",
                        object_text=secondary_label,
                        object_type="role_label",
                        object_ref=None,
                        subject_text=object_text,
                        observation_status="captured",
                        semantic_run_id=semantic_run_id,
                        role_kind=role_kind,
                        extra_identity_fields={"subject_text": object_text},
                    )
                )

        for relation_index, relation in enumerate(relation_candidates_by_event.get(event_id, []), start=1):
            if not isinstance(relation, Mapping):
                continue
            predicate_key = str(relation.get("predicate_key") or "").strip()
            subject = relation.get("subject") if isinstance(relation.get("subject"), Mapping) else {}
            obj = relation.get("object") if isinstance(relation.get("object"), Mapping) else {}
            relation_status = observation_status_from_relation(relation)
            action_label = str(relation.get("display_label") or predicate_key).strip()
            object_text = str(obj.get("canonical_label") or obj.get("canonical_key") or "").strip()
            subject_text = str(subject.get("canonical_label") or subject.get("canonical_key") or "").strip() or None
            if subject_text:
                statement_observations.append(
                    build_relation_observation(
                        run_id=run_id,
                        event_id=event_id,
                        kind="relation_subject",
                        statement_id=statement_id,
                        excerpt_id=excerpt_id,
                        source_id=source_id,
                        observation_order=len(statement_observations) + 1,
                        relation_index=relation_index,
                        predicate_key="actor",
                        predicate_family="actor_identification",
                        object_text=subject_text,
                        object_type=str(subject.get("entity_kind") or "semantic_entity"),
                        object_ref=_normalize_opt_text(subject.get("canonical_key")),
                        subject_text=None,
                        observation_status=relation_status,
                        semantic_run_id=semantic_run_id,
                        relation_candidate_id=relation.get("candidate_id"),
                        source_predicate_key=predicate_key,
                        promotion_status=str(relation.get("promotion_status") or ""),
                        extra_identity_fields={"subject_text": subject_text},
                    )
                )
            if action_label:
                statement_observations.append(
                    build_relation_observation(
                        run_id=run_id,
                        event_id=event_id,
                        kind="relation_action",
                        statement_id=statement_id,
                        excerpt_id=excerpt_id,
                        source_id=source_id,
                        observation_order=len(statement_observations) + 1,
                        relation_index=relation_index,
                        predicate_key="performed_action",
                        predicate_family="actions_events",
                        object_text=action_label,
                        object_type="legal_relation",
                        object_ref=predicate_key,
                        subject_text=subject_text,
                        observation_status=relation_status,
                        semantic_run_id=semantic_run_id,
                        relation_candidate_id=relation.get("candidate_id"),
                        source_predicate_key=predicate_key,
                        promotion_status=str(relation.get("promotion_status") or ""),
                    )
                )
            if predicate_key in {
                "appealed",
                "challenged",
                "heard_by",
                "decided_by",
                "applied",
                "followed",
                "distinguished",
                "held_that",
            }:
                legal_object_text = object_text or action_label
                if legal_object_text:
                    statement_observations.append(
                        build_relation_observation(
                            run_id=run_id,
                            event_id=event_id,
                            kind="legal_relation",
                            statement_id=statement_id,
                            excerpt_id=excerpt_id,
                            source_id=source_id,
                            observation_order=len(statement_observations) + 1,
                            relation_index=relation_index,
                            predicate_key=predicate_key,
                            predicate_family="legal_procedural",
                            object_text=legal_object_text,
                            object_type=str(obj.get("entity_kind") or "legal_relation"),
                            object_ref=_normalize_opt_text(obj.get("canonical_key")) or predicate_key,
                            subject_text=subject_text,
                            observation_status=relation_status,
                            semantic_run_id=semantic_run_id,
                            relation_candidate_id=relation.get("candidate_id"),
                            source_predicate_key=predicate_key,
                            promotion_status=str(relation.get("promotion_status") or ""),
                            extra_identity_fields={"subject_text": subject_text},
                        )
                    )
            if object_text:
                statement_observations.append(
                    build_relation_observation(
                        run_id=run_id,
                        event_id=event_id,
                        kind="relation_object",
                        statement_id=statement_id,
                        excerpt_id=excerpt_id,
                        source_id=source_id,
                        observation_order=len(statement_observations) + 1,
                        relation_index=relation_index,
                        predicate_key="acted_on",
                        predicate_family="object_target",
                        object_text=object_text,
                        object_type=str(obj.get("entity_kind") or "semantic_entity"),
                        object_ref=_normalize_opt_text(obj.get("canonical_key")),
                        subject_text=subject_text,
                        observation_status=relation_status,
                        semantic_run_id=semantic_run_id,
                        relation_candidate_id=relation.get("candidate_id"),
                        source_predicate_key=predicate_key,
                        promotion_status=str(relation.get("promotion_status") or ""),
                    )
                )

        observations.extend(statement_observations)
        fact_candidates.append(
            build_fact_candidate_row(
                run_id=run_id,
                semantic_run_id=semantic_run_id,
                event_id=event_id,
                canonical_label=str(event.get("section") or event.get("text") or "")[:80],
                fact_text=str(event.get("text") or ""),
                fact_type="au_timeline_statement_capture",
                candidate_status=fact_status_for_statement(statement_observations),
                chronology_sort_key=anchor_text,
                chronology_label=anchor_text or str(event.get("event_id") or ""),
                primary_statement_id=statement_id,
                extra_provenance={"section": section} if section else None,
            )
        )

    return build_fact_intake_payload(
        run=run,
        sources=sources,
        excerpts=excerpts,
        statements=statements,
        observations=observations,
        fact_candidates=fact_candidates,
    )


def build_au_fact_review_bundle(
    conn,
    *,
    fact_run_id: str,
    semantic_report: Mapping[str, Any],
    source_events: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    fact_report = build_fact_intake_report(conn, run_id=fact_run_id)
    review_summary = build_fact_review_run_summary(conn, run_id=fact_run_id)
    operator_views = build_fact_review_operator_views(conn, run_id=fact_run_id)
    operator_views["authority_follow"] = _build_authority_follow_operator_view(semantic_report)
    legal_follow_graph = build_au_legal_follow_graph(
        semantic_report,
        source_events=source_events,
    )
    operator_views["legal_follow_graph"] = build_au_legal_follow_operator_view(
        legal_follow_graph
    )
    events = list(fact_report.get("events", [])) if isinstance(fact_report.get("events"), list) else []
    semantic_order = {
        str(row.get("event_id") or ""): index
        for index, row in enumerate(
            source_events if source_events is not None else (
                list(semantic_report.get("per_event", [])) if isinstance(semantic_report.get("per_event"), list) else []
            ),
            start=1,
        )
        if isinstance(row, Mapping)
    }
    chronology = build_event_chronology(events, semantic_order=semantic_order)
    abstentions = build_abstentions(fact_report)
    fact_report_with_abstentions = {**fact_report, "abstentions": abstentions}
    legal_procedural_observations = [
        row
        for row in fact_report.get("observations", [])
        if isinstance(row, Mapping) and str(row.get("predicate_family") or "") == "legal_procedural"
    ]
    legal_procedural_predicates = sorted({str(row.get("predicate_key") or "") for row in legal_procedural_observations if row.get("predicate_key")})
    compiler_contract = build_au_fact_review_bundle_contract(
        fact_report=fact_report_with_abstentions,
        review_summary=review_summary,
        source_documents=list(semantic_report.get("source_documents", []))
        if isinstance(semantic_report.get("source_documents"), list)
        else [],
    )
    promotion_gate = build_product_gate(
        lane="au",
        product_ref="au_fact_review_bundle",
        compiler_contract=compiler_contract,
    )
    suite_normalized_artifact = build_au_fact_review_bundle_normalized_artifact(
        semantic_run_id=str(semantic_report.get("run_id") or ""),
        workflow_kind=str((fact_report.get("run") or {}).get("workflow_link", {}).get("workflow_kind") or ""),
        compiler_contract=compiler_contract,
        promotion_gate=promotion_gate,
        source_documents=list(semantic_report.get("source_documents", []))
        if isinstance(semantic_report.get("source_documents"), list)
        else [],
        typing_deficit_signals=_collect_au_typing_deficit_signals(semantic_report),
    )
    reasoner_input_artifact = build_reasoner_input_artifact(
        source_system="SensibLaw",
        suite_normalized_artifact=suite_normalized_artifact,
        compiler_contract=compiler_contract,
        promotion_gate=promotion_gate,
    )
    review_queue = (
        review_summary.get("review_queue") if isinstance(review_summary.get("review_queue"), list) else []
    )
    default_fact_id = (
        str(review_queue[0].get("fact_id") or "").strip()
        if review_queue and isinstance(review_queue[0], Mapping)
        else None
    )
    workflow_summary = build_bundle_workflow_summary(
        review_summary=review_summary,
        operator_views=operator_views,
        promotion_gate=promotion_gate,
        default_fact_id=default_fact_id,
    )
    review_claim_records = _build_au_review_claim_records(
        review_queue=[row for row in review_queue if isinstance(row, Mapping)],
        run_id=str((fact_report.get("run") or {}).get("run_id") or ""),
        semantic_run_id=str(semantic_report.get("run_id") or ""),
        workflow_summary=workflow_summary,
    )
    return build_fact_review_bundle_payload(
        fact_report=fact_report,
        review_summary=review_summary,
        semantic_run_id=str(semantic_report.get("run_id") or ""),
        source_documents=list(semantic_report.get("source_documents", []))
        if isinstance(semantic_report.get("source_documents"), list)
        else [],
        chronology=chronology,
        abstentions=abstentions,
        operator_views=operator_views,
        workflow_summary=workflow_summary,
        chronology_summary_extras={
            "legal_procedural_observation_count": len(legal_procedural_observations),
            "legal_procedural_predicate_count": len(legal_procedural_predicates),
        },
        compiler_contract=compiler_contract,
        promotion_gate=promotion_gate,
        review_claim_records=review_claim_records,
        semantic_context={
            "summary": dict(semantic_report.get("summary", {}))
            if isinstance(semantic_report.get("summary"), Mapping)
            else {},
            "review_summary": dict(semantic_report.get("review_summary", {}))
            if isinstance(semantic_report.get("review_summary"), Mapping)
            else {},
            "workflow": fact_report["run"].get("workflow_link"),
            "text_debug": dict(semantic_report.get("text_debug", {}))
            if isinstance(semantic_report.get("text_debug"), Mapping)
            else {},
            "au_linkage": dict(semantic_report.get("au_linkage", {}))
            if isinstance(semantic_report.get("au_linkage"), Mapping)
            else {},
            **(
                {
                    "authority_receipts": dict(semantic_report.get("authority_receipts", {}))
                }
                if isinstance(semantic_report.get("authority_receipts"), Mapping)
                else {}
            ),
            "legal_procedural_summary": {
                "observation_count": len(legal_procedural_observations),
                "predicates": legal_procedural_predicates,
                "fact_ids": [
                    row["fact_id"]
                    for row in review_summary.get("review_queue", [])
                    if row.get("has_legal_procedural_observations")
                ],
            },
            "legal_follow_graph": legal_follow_graph,
            "compiler_contract": compiler_contract,
            "promotion_gate": promotion_gate,
            "suite_normalized_artifact": suite_normalized_artifact,
            "reasoner_input_artifact": reasoner_input_artifact,
        },
    )


def build_au_fact_review_bundle_world_model_report(
    review_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(review_bundle, Mapping):
        raise ValueError("world-model report requires AU fact review bundle object")
    if str(review_bundle.get("version") or "").strip() != "fact.review.bundle.v1":
        raise ValueError("world-model report requires AU fact review bundle payload")

    run = review_bundle.get("run", {}) if isinstance(review_bundle.get("run"), Mapping) else {}
    run_id = str(run.get("fact_run_id") or "").strip()
    semantic_run_id = str(run.get("semantic_run_id") or "").strip()
    review_queue = review_bundle.get("review_queue", [])
    if not isinstance(review_queue, Sequence) or isinstance(review_queue, (str, bytes, bytearray)):
        review_queue = []

    claims: list[dict[str, Any]] = []
    for row in review_queue:
        if not isinstance(row, Mapping):
            continue
        claim_id = str(row.get("fact_id") or "").strip()
        if not claim_id:
            continue
        canonical_form = {
            "subject": claim_id,
            "property": "au_review_fact",
            "value": str(row.get("label") or "").strip(),
            "qualifiers": {
                "candidate_status": [str(row.get("candidate_status") or "").strip()],
                "reason_codes": [str(value) for value in row.get("reason_codes", []) if str(value).strip()],
                "policy_outcomes": [str(value) for value in row.get("policy_outcomes", []) if str(value).strip()],
            },
            "references": [],
            "window_id": run_id,
        }
        evidence_paths = [
            {
                "evidence_path_id": f"{claim_id}:{run_id}",
                "run_id": run_id,
                "source_unit_id": claim_id,
                "root_artifact_id": run_id,
                "source_family": "au_fact_review_bundle",
                "authority_level": "review_bundle",
                "provenance_chain": {
                    "run_id": run_id,
                    "semantic_run_id": semantic_run_id,
                    "event_ids": [str(value) for value in row.get("event_ids", []) if str(value).strip()],
                },
                "verification_status": "review_bundle_selected",
            }
        ]
        root_artifact_ids = [run_id] if run_id else []
        claim = {
            "claim_id": claim_id,
            "candidate_id": claim_id,
            "family_id": "au_fact_review_bundle",
            "cohort_id": semantic_run_id,
            "canonical_form": canonical_form,
            "evidence_paths": evidence_paths,
            "independent_count": len(root_artifact_ids),
            "evidence_count": len(evidence_paths),
            "independent_root_artifact_ids": root_artifact_ids,
            "status": "REVIEW_ONLY",
        }
        claim["nat_claim"] = build_nat_claim_dict(
            claim_id=claim_id,
            family_id="au_fact_review_bundle",
            cohort_id=semantic_run_id,
            candidate_id=claim_id,
            canonical_form=canonical_form,
            source_property="review_bundle",
            target_property="review_bundle",
            state="review_claim",
            state_basis="review_bundle",
            root_artifact_id=run_id,
            provenance={
                "source_kind": "review_bundle",
                "run_id": run_id,
                "semantic_run_id": semantic_run_id,
            },
            evidence_status="review_only",
        )
        claim["convergence"] = build_convergence_record(
            claim_id=claim_id,
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=root_artifact_ids,
            claim_status="REVIEW_ONLY",
        )
        claim["temporal"] = build_temporal_envelope(
            claim_id=claim_id,
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=root_artifact_ids,
        )
        claim["conflict_set"] = build_conflict_set(
            claim_id=claim_id,
            candidate_ids=[claim_id],
            evidence_rows=[
                {
                    "run_id": run_id,
                    "root_artifact_id": run_id,
                    "canonical_form": canonical_form,
                }
            ],
        )
        claim["action_policy"] = build_action_policy_record(
            claim_id=claim_id,
            claim_status="REVIEW_ONLY",
            convergence=claim["convergence"],
            temporal=claim["temporal"],
            conflict_set=claim["conflict_set"],
        )
        claims.append(claim)

    return {
        "schema_version": AU_FACT_REVIEW_BUNDLE_WORLD_MODEL_SCHEMA_VERSION,
        "claim_schema_version": NAT_CLAIM_SCHEMA_VERSION,
        "convergence_schema_version": CONVERGENCE_SCHEMA_VERSION,
        "temporal_schema_version": TEMPORAL_SCHEMA_VERSION,
        "conflict_schema_version": CONFLICT_SCHEMA_VERSION,
        "action_policy_schema_version": ACTION_POLICY_SCHEMA_VERSION,
        "run_id": run_id,
        "semantic_run_id": semantic_run_id,
        "claims": claims,
        "summary": {
            "claim_count": len(claims),
            "must_review_count": sum(
                1 for claim in claims if str(claim.get("action_policy", {}).get("actionability") or "") == "must_review"
            ),
        },
    }
