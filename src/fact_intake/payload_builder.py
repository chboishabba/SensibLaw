from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping


def stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_payload(payload: object) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def build_fact_intake_run(
    *,
    run_kind: str,
    semantic_run_id: str,
    per_event: list[Mapping[str, Any]],
    source_documents: list[Mapping[str, Any]],
    source_label: str,
    notes: str,
) -> dict[str, Any]:
    run_basis = {
        "kind": run_kind,
        "semantic_run_id": semantic_run_id,
        "event_ids": [str(row.get("event_id") or "") for row in per_event],
        "source_documents": [str(row.get("sourceDocumentId") or "") for row in source_documents],
    }
    return {
        "run_id": "factrun:" + sha256_payload(run_basis),
        "contract_version": "fact.intake.bundle.v1",
        "source_label": source_label,
        "mary_projection_version": "mary.fact_workflow.v1",
        "notes": notes,
    }


def build_source_rows(
    *,
    run_id: str,
    semantic_run_id: str,
    source_documents: list[Mapping[str, Any]],
    default_source_type: str,
    lexical_mode_for: Callable[[str], str | None],
    extra_document_provenance: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    sources: list[dict[str, Any]] = []
    source_map: dict[str, str] = {}
    for index, document in enumerate(source_documents, start=1):
        source_document_id = str(document.get("sourceDocumentId") or "").strip()
        source_id = build_source_id(run_id=run_id, source_document_id=source_document_id)
        source_map[source_document_id] = source_id
        content_sha = hashlib.sha256(str(document.get("text") or "").encode("utf-8")).hexdigest()
        source_type = str(document.get("sourceType") or default_source_type)
        provenance: dict[str, Any] = {
            "semantic_run_id": semantic_run_id,
            "source_document_id": source_document_id,
        }
        lexical_mode = lexical_mode_for(source_type)
        if lexical_mode:
            provenance["lexical_projection_mode"] = lexical_mode
        if extra_document_provenance is not None:
            provenance.update(dict(extra_document_provenance(document)))
        sources.append(
            {
                "source_id": source_id,
                "source_order": index,
                "source_type": source_type,
                "source_label": str(document.get("title") or source_document_id or f"source_{index}"),
                "source_ref": source_document_id,
                "content_sha256": content_sha,
                "provenance": provenance,
            }
        )
    return sources, source_map


def build_source_id(*, run_id: str, source_document_id: str) -> str:
    return f"src:{sha256_payload({'run_id': run_id, 'source_document_id': source_document_id})[:16]}"


def ensure_event_source_row(
    *,
    sources: list[dict[str, Any]],
    source_map: dict[str, str],
    run_id: str,
    semantic_run_id: str,
    source_document_id: str,
    source_type: str,
    source_text: str,
    lexical_mode_for: Callable[[str], str | None],
    source_document_value: str | None = None,
) -> str:
    source_id = source_map.get(source_document_id)
    if source_id is not None:
        return source_id
    source_id = build_source_id(run_id=run_id, source_document_id=source_document_id)
    source_map[source_document_id] = source_id
    provenance: dict[str, Any] = {
        "semantic_run_id": semantic_run_id,
        "source_document_id": source_document_value,
    }
    lexical_mode = lexical_mode_for(source_type)
    if lexical_mode:
        provenance["lexical_projection_mode"] = lexical_mode
    sources.append(
        {
            "source_id": source_id,
            "source_order": len(sources) + 1,
            "source_type": source_type,
            "source_label": source_document_id or f"source_{len(sources)+1}",
            "source_ref": source_document_value,
            "content_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            "provenance": provenance,
        }
    )
    return source_id


def build_excerpt_row(
    *,
    run_id: str,
    semantic_run_id: str,
    event_id: str,
    source_id: str,
    excerpt_order: int,
    excerpt_text: str,
    char_start: Any,
    char_end: Any,
    anchor_label: str,
    extra_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = {
        "semantic_run_id": semantic_run_id,
        "source_event_id": event_id,
    }
    if extra_provenance:
        provenance.update(dict(extra_provenance))
    return {
        "excerpt_id": f"excerpt:{sha256_payload({'run_id': run_id, 'event_id': event_id, 'kind': 'excerpt'})[:16]}",
        "source_id": source_id,
        "excerpt_order": excerpt_order,
        "excerpt_text": excerpt_text,
        "char_start": char_start,
        "char_end": char_end,
        "anchor_label": anchor_label,
        "provenance": provenance,
    }


def build_statement_row(
    *,
    run_id: str,
    semantic_run_id: str,
    event_id: str,
    excerpt_id: str,
    statement_text: str,
    statement_role: str,
    chronology_hint: str | None,
    extra_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = {
        "semantic_run_id": semantic_run_id,
        "source_event_id": event_id,
    }
    if extra_provenance:
        provenance.update(dict(extra_provenance))
    return {
        "statement_id": f"statement:{sha256_payload({'run_id': run_id, 'event_id': event_id, 'kind': 'statement'})[:16]}",
        "excerpt_id": excerpt_id,
        "statement_order": 1,
        "statement_text": statement_text,
        "speaker_label": None,
        "statement_role": statement_role,
        "statement_status": "captured",
        "chronology_hint": chronology_hint,
        "provenance": provenance,
    }


def build_fact_candidate_row(
    *,
    run_id: str,
    semantic_run_id: str,
    event_id: str,
    canonical_label: str,
    fact_text: str,
    fact_type: str,
    candidate_status: str,
    chronology_sort_key: str | None,
    chronology_label: str,
    primary_statement_id: str,
    extra_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = {
        "semantic_run_id": semantic_run_id,
        "source_event_id": event_id,
    }
    if extra_provenance:
        provenance.update(dict(extra_provenance))
    return {
        "fact_id": f"fact:{sha256_payload({'run_id': run_id, 'event_id': event_id, 'kind': 'fact'})[:16]}",
        "canonical_label": canonical_label,
        "fact_text": fact_text,
        "fact_type": fact_type,
        "candidate_status": candidate_status,
        "chronology_sort_key": chronology_sort_key,
        "chronology_label": chronology_label,
        "primary_statement_id": primary_statement_id,
        "statement_ids": [primary_statement_id],
        "provenance": provenance,
    }


def build_fact_intake_payload(
    *,
    run: Mapping[str, Any],
    sources: list[dict[str, Any]],
    excerpts: list[dict[str, Any]],
    statements: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    fact_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "run": dict(run),
        "sources": sources,
        "excerpts": excerpts,
        "statements": statements,
        "observations": observations,
        "fact_candidates": fact_candidates,
        "contestations": [],
        "reviews": [],
    }
