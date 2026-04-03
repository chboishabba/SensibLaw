"""Bounded follow contract for ICC/ICJ case records."""

from dataclasses import dataclass
from typing import Any, Mapping


def case_record_follow_contract() -> dict[str, str | list[str]]:
    return {
        "scope": "bounded ICC/ICJ case follow unit",
        "constraints": [
            "crossrefs limited to intra-case sections or numbered procedural paragraphs",
            "lineage links limited to explicitly cited instruments, precedents, or docket entries",
            "translation-aware notes stay evidentiary and are never used to promote authority",
        ],
        "authority_signal": "derived-only authority; provenance stays anchored to the ICC/ICJ document metadata",
        "justification": (
            "Keeps the case-record seam focused on the referenced ICC/ICJ filing without expanding into "
            "the broader case law graph or promotional authority."
        ),
    }


@dataclass
class CaseRecordFollowInput:
    case_id: str
    court: str
    title: str
    summary_snippet: str
    crossrefs: list[str]
    lineage_links: list[str]
    translation_notes: list[str]


def normalize_case_record_follow_input(payload: Mapping[str, Any]) -> CaseRecordFollowInput:
    return CaseRecordFollowInput(
        case_id=str(payload.get("case_id") or ""),
        court=str(payload.get("court") or ""),
        title=str(payload.get("title") or ""),
        summary_snippet=str(payload.get("summary_snippet") or "")[:512],
        crossrefs=list(payload.get("crossrefs") or []),
        lineage_links=list(payload.get("lineage_links") or []),
        translation_notes=list(payload.get("translation_notes") or []),
    )
