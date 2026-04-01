from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any, Mapping, Sequence

CROSS_SOURCE_ALIGNMENT_SCHEMA_VERSION = "sl.wikidata_review_packet.cross_source_alignment.v0_1"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _bounded_statement(text: str, *, max_chars: int) -> str:
    normalized = _as_text(text)
    if len(normalized) <= max_chars:
        return normalized
    clipped = normalized[: max_chars - 3].rstrip()
    return f"{clipped}..."


def _extract_identity(source: Mapping[str, Any]) -> str:
    identity_fields = ("qid", "entity_id", "item_id", "primary_qid", "candidate_id")
    for field in identity_fields:
        candidate = source.get(field)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes)):
            for inner in candidate:
                normalized = _as_text(inner)
                if normalized:
                    return normalized
    return ""


def _extract_field_signature(source: Mapping[str, Any]) -> list[str]:
    raw_fields = source.get("fields")
    if not isinstance(raw_fields, Sequence) or isinstance(raw_fields, (str, bytes)):
        return []
    normalized = []
    for field in raw_fields:
        text = _as_text(field)
        if text:
            normalized.append(text)
    return sorted(set(normalized))


def _build_source_profile(
    label: str,
    source: Mapping[str, Any] | None,
    *,
    max_summary_chars: int,
) -> dict[str, Any]:
    safe_source = source if isinstance(source, Mapping) else {}
    identity = _extract_identity(safe_source)
    summary_candidates = (
        safe_source.get("summary"),
        safe_source.get("description"),
        safe_source.get("note"),
        safe_source.get("why"),
    )
    summary_text = ""
    for candidate in summary_candidates:
        if candidate:
            summary_text = _bounded_statement(candidate, max_chars=max_summary_chars)
            break
    return {
        "label": label,
        "source_tag": _as_text(safe_source.get("source")),
        "identity": identity,
        "key_signature": sorted(_as_text(key) for key in safe_source.keys()),
        "field_signature": _extract_field_signature(safe_source),
        "summary": summary_text,
    }


def _pairwise_signature(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    left_label = left["label"]
    right_label = right["label"]
    left_keys = set(left["key_signature"])
    right_keys = set(right["key_signature"])
    left_fields = set(left["field_signature"])
    right_fields = set(right["field_signature"])
    return {
        "pair": f"{left_label} vs {right_label}",
        "shared_keys": sorted(left_keys & right_keys),
        "only_in_left": sorted(left_keys - right_keys),
        "only_in_right": sorted(right_keys - left_keys),
        "field_overlap": sorted(left_fields & right_fields),
    }


def _determine_consensus(identity_values: Sequence[str]) -> tuple[str, str, int]:
    non_empty = [value for value in identity_values if value]
    if not non_empty:
        return "no_consensus", "", 0
    counts = Counter(non_empty)
    identity, max_count = counts.most_common(1)[0]
    if max_count >= len(non_empty) and len(non_empty) >= 2:
        return "full_consensus", identity, max_count
    if max_count >= 2:
        return "partial_consensus", identity, max_count
    return "no_consensus", "", max_count


def summarize_cross_source_alignment(
    *,
    packet_id: str | None = None,
    wiki_surface: Mapping[str, Any] | None = None,
    query_slice: Mapping[str, Any] | None = None,
    split_bundle: Mapping[str, Any] | None = None,
    max_summary_chars: int = 200,
) -> dict[str, Any]:
    sources = [
        ("wiki_surface", wiki_surface),
        ("query_slice", query_slice),
        ("split_bundle", split_bundle),
    ]
    profiles = {
        label: _build_source_profile(label, source, max_summary_chars=max_summary_chars)
        for label, source in sources
    }
    identity_sequence = [profile["identity"] for profile in profiles.values()]
    consensus_level, consensus_identity, consensus_count = _determine_consensus(identity_sequence)

    agreements: list[str] = []
    disagreements: list[str] = []
    if consensus_identity:
        agreements.append(
            f"Shared entity id {consensus_identity} appears in {consensus_count} source(s)."
        )
    elif sum(1 for value in identity_sequence if value) >= 2:
        disagreements.append("No consistent entity identifier spans the reviewed surfaces.")

    field_sets = [set(profile["field_signature"]) for profile in profiles.values() if profile["field_signature"]]
    if len(field_sets) >= 2:
        common_fields = set.intersection(*field_sets)
        if common_fields:
            agreements.append(
                f"Shared field(s) {sorted(common_fields)} appear across the recorded surfaces."
            )
        else:
            disagreements.append(
                "Fields documented on each surface do not overlap, so reviewers should cross-check."
            )
    else:
        common_fields = []
    pairwise_signatures = [
        _pairwise_signature(profiles[left], profiles[right])
        for left, right in combinations(profiles.keys(), 2)
    ]

    return {
        "schema_version": CROSS_SOURCE_ALIGNMENT_SCHEMA_VERSION,
        "packet_id": _as_text(packet_id),
        "consensus_level": consensus_level,
        "consensus_identity": consensus_identity,
        "common_fields": sorted(common_fields) if common_fields else [],
        "agreements": agreements,
        "disagreements": disagreements,
        "profiles": profiles,
        "pairwise_signatures": pairwise_signatures,
    }
