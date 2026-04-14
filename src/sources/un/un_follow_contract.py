"""Bounded UN document follow contract definitions."""

from dataclasses import dataclass
from typing import Any, Mapping

def un_document_follow_contract() -> dict[str, str | list[str]]:
    return {
        "scope": "bounded UN document follow unit",
        "constraints": [
            "crossrefs limited to intra-document sections or numbered paragraphs",
            "upstream treaty/resolution context only when cited directly in the document",
            "translation-derived links remain evidentiary and never promote authority",
        ],
        "authority_signal": "derived-only authority citations; primary UN document text retains provenance",
        "justification": (
            "Focus keeps the UN follow seam limited to the referenced document unit without broad treaty expansion, "
            "aligning with the existing UK/EU evidence posture."
        ),
    }


@dataclass
class UNFollowInput:
    document_id: str
    title: str
    text_snippet: str
    crossrefs: list[str]
    resolution_sources: list[str]
    translation_links: list[str]


def normalize_un_follow_inputs(input_data: Mapping[str, Any]) -> UNFollowInput:
    return UNFollowInput(
        document_id=str(input_data.get("document_id") or ""),
        title=str(input_data.get("title") or ""),
        text_snippet=str(input_data.get("text_snippet") or "")[:512],
        crossrefs=list(input_data.get("crossrefs") or []),
        resolution_sources=list(input_data.get("resolution_sources") or []),
        translation_links=list(input_data.get("translation_links") or []),
    )
