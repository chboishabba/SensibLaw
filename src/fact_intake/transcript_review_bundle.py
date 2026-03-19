from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

from .read_model import build_fact_intake_report, build_fact_review_operator_views, build_fact_review_run_summary

FACT_REVIEW_BUNDLE_VERSION = "fact.review.bundle.v1"

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


def _stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_payload(payload: object) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _normalize_opt_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _lexical_mode(source_type: str) -> str | None:
    return _LEXICAL_MODE_BY_SOURCE_TYPE.get(str(source_type or "").strip())


def _observation_status_from_relation(row: Mapping[str, Any]) -> str:
    promotion_status = str(row.get("promotion_status") or "").strip()
    if promotion_status == "promoted":
        return "captured"
    if promotion_status == "abstained":
        return "abstained"
    return "uncertain"


def _fact_status_for_statement(observations: list[dict[str, Any]]) -> str:
    statuses = {str(row.get("observation_status") or "") for row in observations}
    if "captured" in statuses or "uncertain" in statuses:
        return "candidate"
    if "abstained" in statuses:
        return "abstained"
    return "no_fact"


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
    run_basis = {
        "kind": "transcript_fact_intake_run",
        "semantic_run_id": semantic_run_id,
        "event_ids": [str(row.get("event_id") or "") for row in per_event],
        "source_documents": [str(row.get("sourceDocumentId") or "") for row in source_documents],
    }
    run_id = "factrun:" + _sha256_payload(run_basis)
    source_label_value = source_label or f"transcript_semantic:{semantic_run_id}"

    source_map: dict[str, str] = {}
    sources: list[dict[str, Any]] = []
    for index, document in enumerate(source_documents, start=1):
        source_document_id = str(document.get("sourceDocumentId") or "").strip()
        source_id = f"src:{_sha256_payload({'run_id': run_id, 'source_document_id': source_document_id})[:16]}"
        source_map[source_document_id] = source_id
        content_sha = hashlib.sha256(str(document.get("text") or "").encode("utf-8")).hexdigest()
        sources.append(
            {
                "source_id": source_id,
                "source_order": index,
                "source_type": str(document.get("sourceType") or "transcript_file"),
                "source_label": str(document.get("title") or source_document_id or f"source_{index}"),
                "source_ref": source_document_id,
                "content_sha256": content_sha,
                "provenance": {
                    "semantic_run_id": semantic_run_id,
                    "source_document_id": source_document_id,
                    **({"lexical_projection_mode": _lexical_mode(str(document.get("sourceType") or "transcript_file"))} if _lexical_mode(str(document.get("sourceType") or "transcript_file")) else {}),
                    **(
                        {
                            "source_signal_classes": list(document.get("source_signal_classes", []))
                            if isinstance(document.get("source_signal_classes"), list)
                            else list(document.get("sourceSignalClasses", []))
                        }
                        if isinstance(document.get("source_signal_classes"), list)
                        or isinstance(document.get("sourceSignalClasses"), list)
                        else {}
                    ),
                },
            }
        )

    excerpts: list[dict[str, Any]] = []
    statements: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    fact_candidates: list[dict[str, Any]] = []

    for index, event in enumerate(per_event, start=1):
        event_id = str(event.get("event_id") or "").strip()
        source_document_id = str(event.get("source_document_id") or event.get("source_id") or "").strip()
        source_id = source_map.get(source_document_id)
        if source_id is None:
            source_id = f"src:{_sha256_payload({'run_id': run_id, 'source_document_id': source_document_id})[:16]}"
            source_map[source_document_id] = source_id
            sources.append(
                {
                    "source_id": source_id,
                    "source_order": len(sources) + 1,
                    "source_type": str(event.get("source_type") or "transcript_file"),
                    "source_label": source_document_id or f"source_{len(sources)+1}",
                    "source_ref": source_document_id or None,
                    "content_sha256": hashlib.sha256(str(event.get("text") or "").encode("utf-8")).hexdigest(),
                    "provenance": {
                        "semantic_run_id": semantic_run_id,
                        "source_document_id": source_document_id,
                        **({"lexical_projection_mode": _lexical_mode(str(event.get("source_type") or "transcript_file"))} if _lexical_mode(str(event.get("source_type") or "transcript_file")) else {}),
                    },
                }
            )

        excerpt_id = f"excerpt:{_sha256_payload({'run_id': run_id, 'event_id': event_id, 'kind': 'excerpt'})[:16]}"
        statement_id = f"statement:{_sha256_payload({'run_id': run_id, 'event_id': event_id, 'kind': 'statement'})[:16]}"
        fact_id = f"fact:{_sha256_payload({'run_id': run_id, 'event_id': event_id, 'kind': 'fact'})[:16]}"
        statement_observations: list[dict[str, Any]] = []

        excerpts.append(
            {
                "excerpt_id": excerpt_id,
                "source_id": source_id,
                "excerpt_order": index,
                "excerpt_text": str(event.get("text") or ""),
                "char_start": event.get("source_char_start"),
                "char_end": event.get("source_char_end"),
                "anchor_label": event_id,
                "provenance": {
                    "semantic_run_id": semantic_run_id,
                    "source_event_id": event_id,
                },
            }
        )
        statements.append(
            {
                "statement_id": statement_id,
                "excerpt_id": excerpt_id,
                "statement_order": 1,
                "statement_text": str(event.get("text") or ""),
                "speaker_label": None,
                "statement_role": "transcript_statement",
                "statement_status": "captured",
                "chronology_hint": None,
                "provenance": {
                    "semantic_run_id": semantic_run_id,
                    "source_event_id": event_id,
                },
            }
        )

        for role_index, role in enumerate(event.get("event_roles", []), start=1):
            if not isinstance(role, Mapping):
                continue
            predicate_key = _ROLE_TO_PREDICATE.get(str(role.get("role_kind") or "").strip())
            entity = role.get("entity") if isinstance(role.get("entity"), Mapping) else {}
            object_text = str(entity.get("canonical_label") or entity.get("canonical_key") or "").strip()
            if not predicate_key or not object_text:
                continue
            statement_observations.append(
                {
                    "observation_id": f"obs:{_sha256_payload({'run_id': run_id, 'event_id': event_id, 'kind': 'role', 'index': role_index, 'predicate_key': predicate_key, 'object_text': object_text})[:16]}",
                    "statement_id": statement_id,
                    "excerpt_id": excerpt_id,
                    "source_id": source_id,
                    "observation_order": len(statement_observations) + 1,
                    "predicate_key": predicate_key,
                    "predicate_family": "actor_identification" if predicate_key in {"actor", "co_actor"} else "object_target",
                    "object_text": object_text,
                    "object_type": str(entity.get("entity_kind") or "semantic_entity"),
                    "object_ref": _normalize_opt_text(entity.get("canonical_key")),
                    "subject_text": None,
                    "observation_status": "captured",
                    "provenance": {
                        "semantic_run_id": semantic_run_id,
                        "source_event_id": event_id,
                        "role_kind": str(role.get("role_kind") or ""),
                        **(
                            {"signal_classes": list(role.get("signal_classes", []))}
                            if isinstance(role.get("signal_classes"), list)
                            else {}
                        ),
                    },
                }
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
            relation_status = _observation_status_from_relation(relation)
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
                    {
                        "observation_id": f"obs:{_sha256_payload({'run_id': run_id, 'event_id': event_id, 'kind': 'relation', 'index': relation_index, 'mapped_index': mapped_index, 'predicate_key': observation_predicate, 'object_text': object_text})[:16]}",
                        "statement_id": statement_id,
                        "excerpt_id": excerpt_id,
                        "source_id": source_id,
                        "observation_order": len(statement_observations) + 1,
                        "predicate_key": observation_predicate,
                        "predicate_family": {
                            "communicated": "actions_events",
                            "acted_on": "object_target",
                            "actor_attribute": "actor_identification",
                            "co_actor": "actor_identification",
                        }[observation_predicate],
                        "object_text": object_text,
                        "object_type": str(obj.get("entity_kind") or "semantic_entity"),
                        "object_ref": _normalize_opt_text(obj.get("canonical_key")),
                        "subject_text": _normalize_opt_text(subject.get("canonical_label")),
                        "observation_status": relation_status,
                        "provenance": {
                            "semantic_run_id": semantic_run_id,
                            "source_event_id": event_id,
                            "relation_candidate_id": relation.get("candidate_id"),
                            "source_predicate_key": predicate_key,
                            "promotion_status": str(relation.get("promotion_status") or ""),
                            **(
                                {"signal_classes": list(relation.get("signal_classes", []))}
                                if isinstance(relation.get("signal_classes"), list)
                                else {}
                            ),
                        },
                    }
                )

        observations.extend(statement_observations)
        fact_candidates.append(
            {
                "fact_id": fact_id,
                "canonical_label": str(event.get("text") or "")[:80],
                "fact_text": str(event.get("text") or ""),
                "fact_type": "transcript_statement_capture",
                "candidate_status": _fact_status_for_statement(statement_observations),
                "chronology_sort_key": None,
                "chronology_label": str(event.get("event_id") or ""),
                "primary_statement_id": statement_id,
                "statement_ids": [statement_id],
                "provenance": {
                    "semantic_run_id": semantic_run_id,
                    "source_event_id": event_id,
                },
            }
        )

    return {
        "run": {
            "run_id": run_id,
            "contract_version": "fact.intake.bundle.v1",
            "source_label": source_label_value,
            "mary_projection_version": "mary.fact_workflow.v1",
            "notes": notes or f"Derived from transcript semantic run {semantic_run_id}",
        },
        "sources": sources,
        "excerpts": excerpts,
        "statements": statements,
        "observations": observations,
        "fact_candidates": fact_candidates,
        "contestations": [],
        "reviews": [],
    }


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
    chronology: list[dict[str, Any]] = []
    semantic_order = {
        str(row.get("event_id") or ""): index
        for index, row in enumerate(semantic_report.get("per_event", []), start=1)
        if isinstance(row, Mapping)
    }
    for index, event in enumerate(events, start=1):
        event_id = str(event.get("event_id") or "")
        source_event_ids = [
            str(value)
            for value in event.get("source_event_ids", [])
            if isinstance(value, str) and str(value).strip()
        ]
        semantic_positions = [semantic_order[source_event_id] for source_event_id in source_event_ids if source_event_id in semantic_order]
        chronology.append(
            {
                "order": min(semantic_positions) if semantic_positions else index,
                "event_id": event_id,
                "source_event_ids": source_event_ids,
                "event_type": str(event.get("event_type") or ""),
                "primary_actor": _normalize_opt_text(event.get("primary_actor")),
                "object_text": _normalize_opt_text(event.get("object_text")),
                "time_start": _normalize_opt_text(event.get("time_start")),
                "status": str(event.get("status") or ""),
            }
        )
    chronology.sort(key=lambda row: (row["time_start"] is None, row["time_start"] or "", row["order"], row["event_id"]))
    abstentions = {
        "statement_ids": [
            str(row.get("statement_id") or "")
            for row in fact_report.get("statements", [])
            if isinstance(row, Mapping) and str(row.get("statement_status") or "") == "abstained"
        ],
        "observation_ids": [
            str(row.get("observation_id") or "")
            for row in fact_report.get("observations", [])
            if isinstance(row, Mapping) and str(row.get("observation_status") or "") == "abstained"
        ],
        "fact_ids": [
            str(row.get("fact_id") or "")
            for row in fact_report.get("facts", [])
            if isinstance(row, Mapping) and str(row.get("candidate_status") or "") == "abstained"
        ],
        "counts": {
            "statement_abstentions": sum(
                1
                for row in fact_report.get("statements", [])
                if isinstance(row, Mapping) and str(row.get("statement_status") or "") == "abstained"
            ),
            "observation_abstentions": sum(
                1
                for row in fact_report.get("observations", [])
                if isinstance(row, Mapping) and str(row.get("observation_status") or "") == "abstained"
            ),
            "fact_abstentions": sum(
                1
                for row in fact_report.get("facts", [])
                if isinstance(row, Mapping) and str(row.get("candidate_status") or "") == "abstained"
            ),
        },
    }
    return {
        "version": FACT_REVIEW_BUNDLE_VERSION,
        "run": {
            "fact_run_id": fact_run_id,
            "semantic_run_id": str(semantic_report.get("run_id") or ""),
            "source_label": str(fact_report["run"]["source_label"]),
            "created_at": str(fact_report["run"]["created_at"]),
            "workflow_link": fact_report["run"].get("workflow_link"),
        },
        "summary": {
            **dict(fact_report.get("summary", {})),
            "source_document_count": len(semantic_report.get("source_documents", []))
            if isinstance(semantic_report.get("source_documents"), list)
            else 0,
        },
        "source_documents": list(semantic_report.get("source_documents", []))
        if isinstance(semantic_report.get("source_documents"), list)
        else [],
        "sources": list(fact_report.get("sources", [])),
        "excerpts": list(fact_report.get("excerpts", [])),
        "statements": list(fact_report.get("statements", [])),
        "observations": list(fact_report.get("observations", [])),
        "events": events,
        "facts": list(fact_report.get("facts", [])),
        "chronology": chronology,
        "chronology_groups": dict(review_summary.get("chronology_groups", {})),
        "review_queue": list(review_summary.get("review_queue", [])),
        "operator_views": operator_views,
        "contested_summary": dict(review_summary.get("contested_summary", {})),
        "chronology_summary": {
            **dict(review_summary.get("chronology_summary", {})),
            "bundle_event_count": len(chronology),
            "bundle_dated_event_count": sum(1 for row in chronology if row["time_start"]),
        },
        "abstentions": abstentions,
        "semantic_context": {
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
        },
    }
