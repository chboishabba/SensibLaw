from __future__ import annotations

from typing import Any

from src.ingestion.media_adapter import CanonicalText, ParsedEnvelope, parse_canonical_text
from src.ingestion.section_parser import parse_canonical_section


def _first_text_ref(parsed_envelope: ParsedEnvelope) -> dict[str, Any]:
    units = parsed_envelope.parsed_units
    if units:
        return {
            "text_id": parsed_envelope.canonical_text.text_id,
            "segment_id": units[0].segment_id,
            "unit_id": units[0].unit_id,
            "envelope_id": parsed_envelope.envelope_id,
        }

    segments = parsed_envelope.parsed_segments or parsed_envelope.canonical_text.segments
    if segments:
        return {
            "text_id": parsed_envelope.canonical_text.text_id,
            "segment_id": segments[0].segment_id,
            "envelope_id": parsed_envelope.envelope_id,
        }

    return {
        "text_id": parsed_envelope.canonical_text.text_id,
        "envelope_id": parsed_envelope.envelope_id,
    }


def _statement_id(text_ref: dict[str, Any], number: str | None) -> str:
    suffix = str(number or "statement").strip() or "statement"
    return f"{text_ref['text_id']}:policy_statement:{suffix}"


def _query_id(text_ref: dict[str, Any], suffix: str) -> str:
    return f"{text_ref['text_id']}:ir_query:{suffix}"


def build_normative_policy_extract(
    canonical_text: CanonicalText,
    *,
    ingest_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed_envelope = parse_canonical_text(
        canonical_text,
        parse_profile="normative_policy",
        ingest_receipt=ingest_receipt or {},
    )
    section = parse_canonical_section(canonical_text)
    text_ref = _first_text_ref(parsed_envelope)

    policy_statements: list[dict[str, Any]] = []
    ir_queries: list[dict[str, Any]] = []

    if section.modality:
        statement_id = _statement_id(text_ref, section.number)
        policy_statements.append(
            {
                "statement_id": statement_id,
                "text": section.text,
                "heading": section.heading,
                "section_number": section.number,
                "modality": section.modality,
                "conditions": list(section.conditions),
                "references": [ref.to_citation_dict() for ref in section.references],
                "text_ref": dict(text_ref),
            }
        )
        ir_queries.append(
            {
                "query_id": _query_id(text_ref, "modality"),
                "query_kind": "modality_check",
                "prompt": f"What obligation or permission is stated in: {section.text}",
                "statement_id": statement_id,
                "text_ref": dict(text_ref),
            }
        )

    for index, reference in enumerate(section.references):
        ir_queries.append(
            {
                "query_id": _query_id(text_ref, f"reference:{index}"),
                "query_kind": "reference_lookup",
                "prompt": f"Resolve the cited reference '{reference.citation_text}'.",
                "reference": reference.to_citation_dict(),
                "text_ref": dict(text_ref),
            }
        )

    return {
        "schema_version": "sl.normative_policy_extract.v0_1",
        "parse_profile": parsed_envelope.parse_profile,
        "text_id": canonical_text.text_id,
        "envelope_id": parsed_envelope.envelope_id,
        "policy_statements": policy_statements,
        "ir_queries": ir_queries,
    }


__all__ = ["build_normative_policy_extract"]
