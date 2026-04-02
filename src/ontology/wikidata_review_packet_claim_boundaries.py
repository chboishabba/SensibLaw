from __future__ import annotations

from typing import Any, Mapping, Sequence


WIKIDATA_REVIEW_PACKET_CLAIM_BOUNDARY_SCHEMA_VERSION = (
    "sl.wikidata_review_packet.claim_boundaries.v0_1"
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_anchor_refs(source_surface: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = source_surface.get("anchor_refs", [])
    if not isinstance(raw, list):
        raise ValueError("source_surface.anchor_refs must be a list")
    anchors: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError("each anchor ref must be an object")
        start = int(item.get("start", 0) or 0)
        end = int(item.get("end", 0) or 0)
        anchor_id = _stringify(item.get("anchor_id", f"anchor:{index + 1}")).strip()
        label = _stringify(item.get("label")).strip()
        text_excerpt = _stringify(item.get("text_excerpt")).strip()
        anchors.append(
            {
                "anchor_id": anchor_id or f"anchor:{index + 1}",
                "start": max(start, 0),
                "end": max(end, 0),
                "label": label,
                "text_excerpt": text_excerpt,
            }
        )
    anchors.sort(key=lambda item: (item["start"], item["end"], item["anchor_id"]))
    return anchors


def _normalize_split_axes(split_review_context: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = split_review_context.get("merged_split_axes", [])
    if not isinstance(raw, list):
        raise ValueError("split_review_context.merged_split_axes must be a list")
    axes: list[dict[str, Any]] = []
    for index, axis in enumerate(raw):
        if not isinstance(axis, Mapping):
            raise ValueError("each merged split axis must be an object")
        prop = _stringify(axis.get("property")).strip()
        source = _stringify(axis.get("source")).strip()
        reason = _stringify(axis.get("reason")).strip()
        cardinality = int(axis.get("cardinality", 0) or 0)
        if not prop:
            prop = f"axis_property:{index + 1}"
        axes.append(
            {
                "axis_id": f"axis:{index + 1}",
                "property": prop,
                "source": source,
                "reason": reason,
                "cardinality": max(cardinality, 0),
            }
        )
    axes.sort(key=lambda item: (item["property"], item["source"], item["reason"], item["axis_id"]))
    return axes


def _candidate_missing_evidence(
    *,
    has_anchor_text: bool,
    has_axes: bool,
    has_page_question: bool,
) -> list[str]:
    missing = [
        "no_clause_level_segmentation",
        "no_grounded_claim_assertion",
        "no_cross_source_alignment",
    ]
    if not has_anchor_text:
        missing.append("anchor_excerpt_missing_or_empty")
    if not has_axes:
        missing.append("split_axes_missing")
    if has_page_question:
        missing.append("open_questions_unresolved")
    return sorted(set(missing))


def _review_prompt(*, anchor_label: str, axis_properties: Sequence[str]) -> str:
    if anchor_label and axis_properties:
        return f"Check whether anchor '{anchor_label}' expresses one claim boundary per axis: {', '.join(axis_properties)}."
    if anchor_label:
        return f"Check whether anchor '{anchor_label}' contains one or multiple candidate claim boundaries."
    if axis_properties:
        return f"Check whether split axes ({', '.join(axis_properties)}) imply multiple claim boundaries absent anchor coverage."
    return "Check whether any bounded claim boundary can be justified from the packet surface."


def build_review_packet_claim_boundaries(
    *,
    source_surface: Mapping[str, Any],
    split_review_context: Mapping[str, Any],
    parsed_page: Mapping[str, Any] | None = None,
    page_signals: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(source_surface, Mapping):
        raise ValueError("source_surface must be an object")
    if not isinstance(split_review_context, Mapping):
        raise ValueError("split_review_context must be an object")
    if parsed_page is not None and not isinstance(parsed_page, Mapping):
        raise ValueError("parsed_page must be an object when provided")
    if page_signals is not None and not isinstance(page_signals, Mapping):
        raise ValueError("page_signals must be an object when provided")

    anchors = _normalize_anchor_refs(source_surface)
    axes = _normalize_split_axes(split_review_context)
    unresolved_questions = []
    if isinstance(page_signals, Mapping):
        raw_questions = page_signals.get("unresolved_questions", [])
        if isinstance(raw_questions, list):
            unresolved_questions = [
                _stringify(item).strip() for item in raw_questions if _stringify(item).strip()
            ]

    boundaries: list[dict[str, Any]] = []
    axis_properties = [axis["property"] for axis in axes]

    if anchors:
        for index, anchor in enumerate(anchors):
            boundaries.append(
                {
                    "boundary_id": f"boundary:{index + 1}",
                    "boundary_state": "candidate_only",
                    "anchor_ref": {
                        "anchor_id": anchor["anchor_id"],
                        "start": anchor["start"],
                        "end": anchor["end"],
                        "label": anchor["label"] or None,
                    },
                    "axis_signals": [dict(axis) for axis in axes],
                    "candidate_claim_text": anchor["text_excerpt"],
                    "review_prompt": _review_prompt(
                        anchor_label=anchor["label"],
                        axis_properties=axis_properties,
                    ),
                    "missing_evidence": _candidate_missing_evidence(
                        has_anchor_text=bool(anchor["text_excerpt"]),
                        has_axes=bool(axes),
                        has_page_question=bool(unresolved_questions),
                    ),
                }
            )
    elif axes:
        boundaries.append(
            {
                "boundary_id": "boundary:axis-only:1",
                "boundary_state": "candidate_only",
                "anchor_ref": None,
                "axis_signals": [dict(axis) for axis in axes],
                "candidate_claim_text": "",
                "review_prompt": _review_prompt(
                    anchor_label="",
                    axis_properties=axis_properties,
                ),
                "missing_evidence": sorted(
                    set(
                        _candidate_missing_evidence(
                            has_anchor_text=False,
                            has_axes=True,
                            has_page_question=bool(unresolved_questions),
                        )
                        + ["no_anchor_refs_for_axis_mapping"]
                    )
                ),
            }
        )

    return {
        "schema_version": WIKIDATA_REVIEW_PACKET_CLAIM_BOUNDARY_SCHEMA_VERSION,
        "decomposition_state": "candidate_only",
        "non_claims": [
            "not_full_semantic_decomposition",
            "not_claim_truth_evaluation",
            "not_execution_ready_migration_logic",
        ],
        "candidate_claim_boundaries": boundaries,
        "summary": {
            "anchor_count": len(anchors),
            "axis_count": len(axes),
            "candidate_boundary_count": len(boundaries),
            "unresolved_question_count": len(unresolved_questions),
        },
    }


__all__ = [
    "WIKIDATA_REVIEW_PACKET_CLAIM_BOUNDARY_SCHEMA_VERSION",
    "build_review_packet_claim_boundaries",
]
