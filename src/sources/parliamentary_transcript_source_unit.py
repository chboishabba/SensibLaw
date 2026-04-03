from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.sources.normalized_source import build_normalized_source_unit


@dataclass(frozen=True)
class ClauseIR:
    clause_label: str
    clause_reference: str
    interpretive_note: str
    legal_claim_type: str
    language: str = "en"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value or "")).strip("_").lower() or "unknown"


def build_parliamentary_source_unit_from_transcript(
    *,
    transcript_id: str,
    utterance_index: int,
    session_label: str,
    session_url: str,
    speaker_name: str,
    speaker_role: str,
    statement_text: str,
    claim_type: str,
    jurisdiction: str,
    source_family: str,
    clause_ir: ClauseIR,
    authority_level: str = "parliamentary_interpretive",
    timestamp: str | None = None,
) -> dict[str, Any]:
    source_unit_id = (
        f"sourceunit:parliamentary:{_slug(transcript_id)}:{_slug(speaker_name)}:{utterance_index}"
    )
    normalized = build_normalized_source_unit(
        source_id=source_unit_id,
        source_family=source_family,
        jurisdiction=jurisdiction,
        authority_level=authority_level,
        source_type="parliamentary_statement",
        title=f"{speaker_name} ({speaker_role}) in {session_label}",
        url=session_url,
        section=clause_ir.clause_reference,
        version=f"{transcript_id}:{utterance_index}",
        live_status="snapshot",
        primary_language=clause_ir.language,
        translation_status="original",
        provenance=f"transcript:{transcript_id}",
        readiness_signals={
            "speaker_role": speaker_role,
            "claim_type": claim_type,
            "timestamp_provided": bool(timestamp),
        },
    )
    speaker_identity = {
        "name": speaker_name,
        "role": speaker_role,
    }
    return {
        "source_unit_id": source_unit_id,
        "normalized_source_unit": normalized,
        "speaker_identity": speaker_identity,
        "claim_type": claim_type,
        "clause_ir": clause_ir.to_dict(),
        "statement_snippet": statement_text.strip()[:256],
        "session_label": session_label,
        "timestamp": timestamp,
    }
