from __future__ import annotations

import hashlib
from typing import Any, Mapping

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
    build_event_chronology,
    build_fact_review_bundle_payload,
)
from .projection_helpers import (
    build_relation_observation,
    build_role_observation,
    fact_status_for_statement,
    observation_status_from_relation,
)

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

def _normalize_opt_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _lexical_mode(source_type: str) -> str | None:
    return _LEXICAL_MODE_BY_SOURCE_TYPE.get(str(source_type or "").strip())


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
        authority_term_tokens = [
            str(value)
            for value in row.get("authority_term_tokens", [])
            if isinstance(value, str) and str(value).strip()
        ]
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
                    {"label": "Titles", "value": ", ".join(authority_titles)},
                    {"label": "Legal refs", "value": ", ".join(legal_refs)},
                    {"label": "Terms", "value": ", ".join(authority_term_tokens)},
                ],
                extra={
                    "event_id": str(row.get("event_id") or ""),
                    "event_section": _normalize_opt_text(row.get("event_section")),
                    "event_text": _normalize_opt_text(row.get("event_text")),
                    "resolution_hint": str(row.get("resolution_hint") or ""),
                    "candidate_citations": candidate_citations,
                    "authority_titles": authority_titles,
                    "legal_refs": legal_refs,
                    "authority_term_tokens": authority_term_tokens,
                },
            )
        )
    queue_summary = summarize_follow_queue(queue)
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
            "route_target_counts": queue_summary["route_target_counts"],
            "resolution_status_counts": queue_summary["resolution_status_counts"],
            "queue_count": queue_summary["queue_count"],
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
    legal_procedural_observations = [
        row
        for row in fact_report.get("observations", [])
        if isinstance(row, Mapping) and str(row.get("predicate_family") or "") == "legal_procedural"
    ]
    legal_procedural_predicates = sorted({str(row.get("predicate_key") or "") for row in legal_procedural_observations if row.get("predicate_key")})
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
        chronology_summary_extras={
            "legal_procedural_observation_count": len(legal_procedural_observations),
            "legal_procedural_predicate_count": len(legal_procedural_predicates),
        },
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
        },
    )
