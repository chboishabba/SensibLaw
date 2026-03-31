from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping

from .read_model import build_fact_intake_report, build_fact_review_operator_views, build_fact_review_run_summary
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
from .review_bundle import (
    FACT_REVIEW_BUNDLE_VERSION,
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
    "speaker": "actor",
    "subject": "actor",
    "mentioned_entity": "co_actor",
    "related_person": "co_actor",
    "theme": "subject_matter",
}

_RELATION_TO_OBSERVATIONS = {
    "replied_to": ("communicated", "acted_on"),
    "felt_state": ("actor_attribute",),
    "sibling_of": ("actor_attribute", "co_actor"),
    "parent_of": ("actor_attribute", "co_actor"),
    "child_of": ("actor_attribute", "co_actor"),
    "spouse_of": ("actor_attribute", "co_actor"),
    "friend_of": ("actor_attribute", "co_actor"),
    "guardian_of": ("actor_attribute", "co_actor"),
    "caregiver_of": ("actor_attribute", "co_actor"),
}

_RELATION_EVENT_TYPE = {
    "replied_to": "communication",
}

_LEXICAL_MODE_BY_SOURCE_TYPE = {
    "chat_archive_sample": "chat_archive",
    "facebook_messages_archive_sample": "chat_archive",
    "openrecall_capture": "chat_archive",
    "transcript_file": "transcript_handoff",
    "interview_note": "transcript_handoff",
    "support_worker_note": "transcript_handoff",
    "annotation_note": "transcript_handoff",
    "professional_note": "transcript_handoff",
    "professional_interpretation": "transcript_handoff",
}

def _normalize_opt_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _lexical_mode(source_type: str) -> str | None:
    return _LEXICAL_MODE_BY_SOURCE_TYPE.get(str(source_type or "").strip())


def build_fact_intake_payload_from_transcript_report(
    report: Mapping[str, Any],
    *,
    source_label: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    semantic_run_id = str(report.get("run_id") or "").strip()
    if not semantic_run_id:
        raise ValueError("transcript semantic report run_id is required")
    per_event = list(report.get("per_event", [])) if isinstance(report.get("per_event"), list) else []
    source_documents = list(report.get("source_documents", [])) if isinstance(report.get("source_documents"), list) else []
    run = build_fact_intake_run(
        run_kind="transcript_fact_intake_run",
        semantic_run_id=semantic_run_id,
        per_event=per_event,
        source_documents=source_documents,
        source_label=source_label or f"transcript_semantic:{semantic_run_id}",
        notes=notes or f"Derived from transcript semantic run {semantic_run_id}",
    )
    run_id = str(run["run_id"])

    def _extra_document_provenance(document: Mapping[str, Any]) -> Mapping[str, Any]:
        if isinstance(document.get("source_signal_classes"), list):
            return {"source_signal_classes": list(document.get("source_signal_classes", []))}
        if isinstance(document.get("sourceSignalClasses"), list):
            return {"source_signal_classes": list(document.get("sourceSignalClasses", []))}
        return {}

    sources, source_map = build_source_rows(
        run_id=run_id,
        semantic_run_id=semantic_run_id,
        source_documents=source_documents,
        default_source_type="transcript_file",
        lexical_mode_for=_lexical_mode,
        extra_document_provenance=_extra_document_provenance,
    )

    excerpts: list[dict[str, Any]] = []
    statements: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    fact_candidates: list[dict[str, Any]] = []

    for index, event in enumerate(per_event, start=1):
        event_id = str(event.get("event_id") or "").strip()
        source_document_id = str(event.get("source_document_id") or event.get("source_id") or "").strip()
        source_id = ensure_event_source_row(
            sources=sources,
            source_map=source_map,
            run_id=run_id,
            semantic_run_id=semantic_run_id,
            source_document_id=source_document_id,
            source_type=str(event.get("source_type") or "transcript_file"),
            source_text=str(event.get("text") or ""),
            lexical_mode_for=_lexical_mode,
            source_document_value=source_document_id,
        )
        statement_observations: list[dict[str, Any]] = []

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
        )
        statement = build_statement_row(
            run_id=run_id,
            semantic_run_id=semantic_run_id,
            event_id=event_id,
            excerpt_id=str(excerpt["excerpt_id"]),
            statement_text=str(event.get("text") or ""),
            statement_role="transcript_statement",
            chronology_hint=None,
        )
        excerpt_id = str(excerpt["excerpt_id"])
        statement_id = str(statement["statement_id"])
        excerpts.append(excerpt)
        statements.append(statement)

        for role_index, role in enumerate(event.get("event_roles", []), start=1):
            if not isinstance(role, Mapping):
                continue
            predicate_key = _ROLE_TO_PREDICATE.get(str(role.get("role_kind") or "").strip())
            entity = role.get("entity") if isinstance(role.get("entity"), Mapping) else {}
            object_text = str(entity.get("canonical_label") or entity.get("canonical_key") or "").strip()
            if not predicate_key or not object_text:
                continue
            statement_observations.append(
                build_role_observation(
                    run_id=run_id,
                    event_id=event_id,
                    statement_id=statement_id,
                    excerpt_id=excerpt_id,
                    source_id=source_id,
                    observation_order=len(statement_observations) + 1,
                    role_index=role_index,
                    predicate_key=predicate_key,
                    predicate_family="actor_identification" if predicate_key in {"actor", "co_actor"} else "object_target",
                    object_text=object_text,
                    object_type=str(entity.get("entity_kind") or "semantic_entity"),
                    object_ref=_normalize_opt_text(entity.get("canonical_key")),
                    subject_text=None,
                    observation_status="captured",
                    semantic_run_id=semantic_run_id,
                    role_kind=str(role.get("role_kind") or ""),
                    extra_provenance=(
                        {"signal_classes": list(role.get("signal_classes", []))}
                        if isinstance(role.get("signal_classes"), list)
                        else {}
                    ),
                )
            )

        for relation_index, relation in enumerate(event.get("relation_candidates", []), start=1):
            if not isinstance(relation, Mapping):
                continue
            predicate_key = str(relation.get("predicate_key") or "").strip()
            mapped = _RELATION_TO_OBSERVATIONS.get(predicate_key, ())
            if not mapped:
                continue
            subject = relation.get("subject") if isinstance(relation.get("subject"), Mapping) else {}
            obj = relation.get("object") if isinstance(relation.get("object"), Mapping) else {}
            relation_status = observation_status_from_relation(relation)
            for mapped_index, observation_predicate in enumerate(mapped, start=1):
                if observation_predicate == "communicated":
                    object_text = _RELATION_EVENT_TYPE.get(predicate_key, str(relation.get("display_label") or predicate_key))
                elif observation_predicate == "acted_on":
                    object_text = str(obj.get("canonical_label") or obj.get("canonical_key") or "").strip()
                elif observation_predicate == "actor_attribute":
                    object_text = str(obj.get("canonical_label") or predicate_key).strip()
                elif observation_predicate == "co_actor":
                    object_text = str(obj.get("canonical_label") or obj.get("canonical_key") or "").strip()
                else:
                    object_text = str(obj.get("canonical_label") or str(relation.get("display_label") or predicate_key)).strip()
                if not object_text:
                    continue
                statement_observations.append(
                    build_relation_observation(
                        run_id=run_id,
                        event_id=event_id,
                        kind="relation",
                        statement_id=statement_id,
                        excerpt_id=excerpt_id,
                        source_id=source_id,
                        observation_order=len(statement_observations) + 1,
                        relation_index=relation_index,
                        predicate_key=observation_predicate,
                        predicate_family={
                            "communicated": "actions_events",
                            "acted_on": "object_target",
                            "actor_attribute": "actor_identification",
                            "co_actor": "actor_identification",
                        }[observation_predicate],
                        object_text=object_text,
                        object_type=str(obj.get("entity_kind") or "semantic_entity"),
                        object_ref=_normalize_opt_text(obj.get("canonical_key")),
                        subject_text=_normalize_opt_text(subject.get("canonical_label")),
                        observation_status=relation_status,
                        semantic_run_id=semantic_run_id,
                        relation_candidate_id=relation.get("candidate_id"),
                        source_predicate_key=predicate_key,
                        promotion_status=str(relation.get("promotion_status") or ""),
                        extra_identity_fields={"mapped_index": mapped_index},
                        extra_provenance={
                            "semantic_basis": str(relation.get("semantic_basis") or ""),
                            "canonical_promotion_status": str(relation.get("canonical_promotion_status") or ""),
                            "canonical_promotion_basis": str(relation.get("canonical_promotion_basis") or ""),
                            "canonical_promotion_reason": str(relation.get("canonical_promotion_reason") or ""),
                            "semantic_candidate": dict(relation.get("semantic_candidate", {}))
                            if isinstance(relation.get("semantic_candidate"), Mapping)
                            else None,
                            **(
                                {"signal_classes": list(relation.get("signal_classes", []))}
                                if isinstance(relation.get("signal_classes"), list)
                                else {}
                            ),
                        },
                    )
                )

        observations.extend(statement_observations)
        fact_candidates.append(
            build_fact_candidate_row(
                run_id=run_id,
                semantic_run_id=semantic_run_id,
                event_id=event_id,
                canonical_label=str(event.get("text") or "")[:80],
                fact_text=str(event.get("text") or ""),
                fact_type="transcript_statement_capture",
                candidate_status=fact_status_for_statement(statement_observations),
                chronology_sort_key=None,
                chronology_label=str(event.get("event_id") or ""),
                primary_statement_id=statement_id,
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


def build_transcript_fact_review_bundle(
    conn,
    *,
    fact_run_id: str,
    semantic_report: Mapping[str, Any],
) -> dict[str, Any]:
    fact_report = build_fact_intake_report(conn, run_id=fact_run_id)
    review_summary = build_fact_review_run_summary(conn, run_id=fact_run_id)
    operator_views = build_fact_review_operator_views(conn, run_id=fact_run_id)
    events = list(fact_report.get("events", [])) if isinstance(fact_report.get("events"), list) else []
    semantic_order = {
        str(row.get("event_id") or ""): index
        for index, row in enumerate(semantic_report.get("per_event", []), start=1)
        if isinstance(row, Mapping)
    }
    chronology = build_event_chronology(events, semantic_order=semantic_order)
    abstentions = build_abstentions(fact_report)
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
            "relation_candidates": [
                {
                    "candidate_id": row.get("candidate_id"),
                    "event_id": row.get("event_id"),
                    "predicate_key": row.get("predicate_key"),
                    "promotion_status": row.get("promotion_status"),
                    "semantic_basis": row.get("semantic_basis"),
                    "canonical_promotion_status": row.get("canonical_promotion_status"),
                    "canonical_promotion_basis": row.get("canonical_promotion_basis"),
                    "canonical_promotion_reason": row.get("canonical_promotion_reason"),
                    "semantic_candidate": dict(row.get("semantic_candidate", {}))
                    if isinstance(row.get("semantic_candidate"), Mapping)
                    else None,
                }
                for row in semantic_report.get("relation_candidates", [])
                if isinstance(row, Mapping)
            ],
        },
    )
