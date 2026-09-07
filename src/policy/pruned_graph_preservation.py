"""Query-family preservation receipts for pruned external graph artifacts.

A pruned artifact is not automatically complete for queries over its source.
The generic safe direction is soundness: an answer retained in a deletion-only
artifact may be supported upstream. Completeness — including absence reasoning —
requires a revision-bound certificate for the declared query family.

This boundary is inspired by RequestProject.CompilerPipeline, where compiled
relation-word answers are monotone into the source base while stronger equality
results are separately proved for specific stages/corpora.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

PRUNED_GRAPH_PRESERVATION_SCHEMA_VERSION = "sl.pruned_graph_preservation.v0_1"
PRESERVATION_STATES = frozenset({"sound_only", "sound_and_complete", "unverified"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_query_family_preservation_receipt(
    *,
    source_artifact_ref: str,
    source_revision_ref: str,
    pruned_artifact_ref: str,
    pruned_revision_ref: str,
    query_family_ref: str,
    preservation_state: str,
    soundness_receipt_ref: str | None = None,
    completeness_receipt_ref: str | None = None,
    covered_relations: Sequence[str] = (),
    diagnostics: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    state = _text(preservation_state)
    if state not in PRESERVATION_STATES:
        raise ValueError(f"unsupported preservation_state: {state}")
    required = {
        "source_artifact_ref": _text(source_artifact_ref),
        "source_revision_ref": _text(source_revision_ref),
        "pruned_artifact_ref": _text(pruned_artifact_ref),
        "pruned_revision_ref": _text(pruned_revision_ref),
        "query_family_ref": _text(query_family_ref),
    }
    if not all(required.values()):
        raise ValueError("query-family preservation requires artifact, revision and family references")
    soundness = _text(soundness_receipt_ref)
    completeness = _text(completeness_receipt_ref)
    if state in {"sound_only", "sound_and_complete"} and not soundness:
        raise ValueError("sound preservation requires soundness_receipt_ref")
    if state == "sound_and_complete" and not completeness:
        raise ValueError("complete preservation requires completeness_receipt_ref")
    if state != "sound_and_complete" and completeness:
        raise ValueError("completeness_receipt_ref requires sound_and_complete state")

    return {
        "schema_version": PRUNED_GRAPH_PRESERVATION_SCHEMA_VERSION,
        **required,
        "preservation_state": state,
        "covered_relations": sorted({_text(value) for value in covered_relations if _text(value)}),
        "soundness_receipt_ref": soundness or None,
        "completeness_receipt_ref": completeness or None,
        "sound_for_positive_answers": state in {"sound_only", "sound_and_complete"},
        "complete_for_negative_answers": state == "sound_and_complete",
        "diagnostics": [deepcopy(dict(row)) for row in diagnostics if isinstance(row, Mapping)],
        "authority": "diagnostic_only",
        "promotion_effect": "not_evaluated",
        "edit_effect": "none",
    }


def preservation_allows_absence(
    receipt: Mapping[str, Any], *, query_family_ref: str
) -> bool:
    """True only for the exact family named by a sound+complete receipt."""

    return bool(
        _text(receipt.get("schema_version")) == PRUNED_GRAPH_PRESERVATION_SCHEMA_VERSION
        and _text(receipt.get("query_family_ref")) == _text(query_family_ref)
        and _text(receipt.get("preservation_state")) == "sound_and_complete"
        and _text(receipt.get("soundness_receipt_ref"))
        and _text(receipt.get("completeness_receipt_ref"))
    )


__all__ = [
    "PRUNED_GRAPH_PRESERVATION_SCHEMA_VERSION",
    "PRESERVATION_STATES",
    "build_query_family_preservation_receipt",
    "preservation_allows_absence",
]
