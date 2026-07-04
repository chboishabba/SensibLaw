"""Affidavit adapter over the shared hint surface."""
from __future__ import annotations

from .hint_surface import (
    DEFAULT_ANCHOR_KIND_WEIGHT,
    DEFAULT_WORKLOAD_CLASS_PRIORITY,
    MONTH_PATTERN,
    PROCEDURAL_EVENT_KEYWORDS,
    build_candidate_anchors,
    build_provisional_anchor_bundles,
    build_provisional_structured_anchors,
    classify_workload_with_hints,
    extract_extraction_hints,
    recommend_next_action,
)


__all__ = [
    "DEFAULT_ANCHOR_KIND_WEIGHT",
    "DEFAULT_WORKLOAD_CLASS_PRIORITY",
    "MONTH_PATTERN",
    "PROCEDURAL_EVENT_KEYWORDS",
    "build_candidate_anchors",
    "build_provisional_anchor_bundles",
    "build_provisional_structured_anchors",
    "classify_workload_with_hints",
    "extract_extraction_hints",
    "recommend_next_action",
]
