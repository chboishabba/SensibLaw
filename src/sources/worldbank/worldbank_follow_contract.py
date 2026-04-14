"""World Bank follow contract for normalized document units."""

from dataclasses import dataclass
from typing import Any, Mapping


def worldbank_follow_contract() -> dict[str, str | list[str]]:
    return {
        "scope": "bounded World Bank document follow",
        "constraints": [
            "crossrefs limited to intra-document sections and numbered references",
            "report/policy lineage only when cited directly or via project appendices",
            "non-promotive language: diagnostics and translations stay evidentiary",
        ],
        "authority_signal": "derived-only authority citations; World Bank project/publication metadata carries provenance",
        "justification": (
            "Focus keeps the World Bank seam evidentiary and constrained to the cited report/policy unit "
            "without expanding into broader policy graphs."
        ),
    }


@dataclass
class WorldBankFollowInput:
    document_id: str
    title: str
    summary_snippet: str
    crossrefs: list[str]
    lineage_refs: list[str]
    translation_notes: list[str]


def normalize_worldbank_follow_input(payload: Mapping[str, Any]) -> WorldBankFollowInput:
    return WorldBankFollowInput(
        document_id=str(payload.get("document_id") or ""),
        title=str(payload.get("title") or ""),
        summary_snippet=str(payload.get("summary_snippet") or "")[:512],
        crossrefs=list(payload.get("crossrefs") or []),
        lineage_refs=list(payload.get("lineage_refs") or []),
        translation_notes=list(payload.get("translation_notes") or []),
    )
