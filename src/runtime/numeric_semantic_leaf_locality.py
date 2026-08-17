"""Audit-only locality comparison for portable numeric semantic leaves.

This module is deliberately not a receipt authority.  It compares two audit
projections emitted from the closed numeric authority and records whether the
semantic leaves that changed are reachable from the source edit boundary.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping

from sensiblaw.interfaces import tokenize_canonical_with_spans


def _nodes(value: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = value.get("nodes")
    if not isinstance(rows, list):
        raise ValueError("numeric leaf audit requires nodes")
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("ref"), str):
            raise ValueError("numeric leaf audit node is malformed")
        result[str(row["ref"])] = row
    return result


def _spans(row: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    result: list[tuple[int, int]] = []
    for value in row.get("source_spans") or ():
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("numeric leaf audit source span is malformed")
        start, end = int(value[0]), int(value[1])
        if start < 0 or end < start:
            raise ValueError("numeric leaf audit source span is invalid")
        result.append((start, end))
    return tuple(result)


def _affected_spans(
    before: str, after: str
) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...], dict[int, int]]:
    left = tokenize_canonical_with_spans(before)
    right = tokenize_canonical_with_spans(after)
    matcher = SequenceMatcher(
        None,
        [token for token, _start, _end in left],
        [token for token, _start, _end in right],
        autojunk=False,
    )
    left_spans: list[tuple[int, int]] = []
    right_spans: list[tuple[int, int]] = []
    aligned: dict[int, int] = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            aligned.update({index: i1 + index - j1 for index in range(j1, j2)})
            continue
        left_spans.extend((start, end) for _token, start, end in left[i1:i2])
        right_spans.extend((start, end) for _token, start, end in right[j1:j2])
        # Insertions and deletions have an empty span on one side.  The
        # nearest token makes the containing parser sentence an edit boundary.
        if i1 == i2 and left:
            anchor = min(i1, len(left) - 1)
            left_spans.append((left[anchor][1], left[anchor][2]))
        if j1 == j2 and right:
            anchor = min(j1, len(right) - 1)
            right_spans.append((right[anchor][1], right[anchor][2]))
    return tuple(left_spans), tuple(right_spans), aligned


def _sentence_boundary(
    audit: Mapping[str, Any], spans: Iterable[tuple[int, int]]
) -> tuple[tuple[int, int], ...]:
    sentences = audit.get("parser_sentence_spans") or ()
    source = tuple(spans)
    selected: list[tuple[int, int]] = []
    for value in sentences:
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("numeric leaf audit sentence span is malformed")
        start, end = int(value[0]), int(value[1])
        if any(
            start <= changed_end and changed_start <= end
            for changed_start, changed_end in source
        ):
            selected.append((start, end))
    return tuple(selected or source)


def _overlaps(
    spans: Iterable[tuple[int, int]], boundary: Iterable[tuple[int, int]]
) -> bool:
    return any(
        start <= other_end and other_start <= end
        for start, end in spans
        for other_start, other_end in boundary
    )


def _source_key(
    row: Mapping[str, Any],
    tokens: list[tuple[str, int, int]],
    to_left: Mapping[int, int] | None,
) -> tuple[int, ...] | None:
    ordinals: list[int] = []
    for start, end in _spans(row):
        for ordinal, (_token, token_start, token_end) in enumerate(tokens):
            if start < token_end and token_start < end:
                if to_left is not None and ordinal not in to_left:
                    return None
                ordinals.append(to_left[ordinal] if to_left is not None else ordinal)
    return tuple(ordinals) if ordinals else None


def _seed_and_closure(
    nodes: Mapping[str, Mapping[str, Any]], boundary: tuple[tuple[int, int], ...]
) -> set[str]:
    reverse: dict[str, set[str]] = {ref: set() for ref in nodes}
    for ref, row in nodes.items():
        for dependency in row.get("dependencies") or ():
            if dependency in reverse:
                reverse[str(dependency)].add(ref)
    reached = {ref for ref, row in nodes.items() if _overlaps(_spans(row), boundary)}
    pending = list(reached)
    while pending:
        ref = pending.pop()
        for dependent in reverse[ref]:
            if dependent not in reached:
                reached.add(dependent)
                pending.append(dependent)
    return reached


def compare_leaf_locality(
    cold_audit: Mapping[str, Any],
    edit_audit: Mapping[str, Any],
    *,
    cold_text: str,
    edit_text: str,
) -> dict[str, Any]:
    """Compare audit leaves under a deterministic source-token alignment."""

    if (
        cold_audit.get("schema_version") != "sensiblaw.numeric-semantic-leaf-audit.v1"
        or edit_audit.get("schema_version")
        != "sensiblaw.numeric-semantic-leaf-audit.v1"
    ):
        return {
            "state": "indeterminate",
            "reason": "unsupported_audit_schema",
            "claim_made": False,
        }
    cold_nodes, edit_nodes = _nodes(cold_audit), _nodes(edit_audit)
    cold_changed, edit_changed, edit_to_cold = _affected_spans(cold_text, edit_text)
    cold_boundary = _sentence_boundary(cold_audit, cold_changed)
    edit_boundary = _sentence_boundary(edit_audit, edit_changed)
    cold_closure = _seed_and_closure(cold_nodes, cold_boundary)
    edit_closure = _seed_and_closure(edit_nodes, edit_boundary)
    cold_tokens, edit_tokens = (
        tokenize_canonical_with_spans(cold_text),
        tokenize_canonical_with_spans(edit_text),
    )

    def group(
        nodes: Mapping[str, Mapping[str, Any]],
        tokens: list[tuple[str, int, int]],
        mapping: Mapping[int, int] | None,
    ):
        grouped: dict[tuple[str, tuple[int, ...]], list[str]] = {}
        for ref, row in nodes.items():
            key = _source_key(row, tokens, mapping)
            if key is not None:
                grouped.setdefault(
                    (str(row.get("family")), str(row.get("shape") or ""), key), []
                ).append(ref)
        return grouped

    cold_groups, edit_groups = (
        group(cold_nodes, cold_tokens, None),
        group(edit_nodes, edit_tokens, edit_to_cold),
    )
    pairs: dict[str, str] = {}
    ambiguous = 0
    for key in set(cold_groups) | set(edit_groups):
        left, right = cold_groups.get(key, ()), edit_groups.get(key, ())
        if len(left) == len(right) == 1:
            pairs[left[0]] = right[0]
        elif left and right:
            ambiguous += 1
    # Source-free leaves (exports/proofs) are matched once their dependency
    # shape is already paired.  This deliberately refuses duplicate shapes.
    for _ in range(len(cold_nodes) + len(edit_nodes)):
        additions = {}
        for left_ref, left in cold_nodes.items():
            if left_ref in pairs or _spans(left):
                continue
            left_dependencies = tuple(
                pairs.get(str(ref)) for ref in left.get("dependencies") or ()
            )
            if any(value is None for value in left_dependencies):
                continue
            candidates = [
                right_ref
                for right_ref, right in edit_nodes.items()
                if right_ref not in pairs.values()
                and not _spans(right)
                and right.get("family") == left.get("family")
                and tuple(right.get("dependencies") or ()) == left_dependencies
            ]
            if len(candidates) == 1:
                additions[left_ref] = candidates[0]
            elif len(candidates) > 1:
                ambiguous += 1
        if not additions:
            break
        pairs.update(additions)

    changed_cold = {ref for ref in cold_nodes if ref not in pairs}
    changed_edit = {ref for ref in edit_nodes if ref not in pairs.values()}
    for left_ref, right_ref in pairs.items():
        if cold_nodes[left_ref].get("digest_sha256") != edit_nodes[right_ref].get(
            "digest_sha256"
        ):
            changed_cold.add(left_ref)
            changed_edit.add(right_ref)
    outside_cold, outside_edit = (
        changed_cold - cold_closure,
        changed_edit - edit_closure,
    )
    state = (
        "indeterminate"
        if ambiguous
        else "verified"
        if not outside_cold and not outside_edit
        else "violated"
    )
    return {
        "state": state,
        "claim_made": state == "verified",
        "matching_ambiguity_count": ambiguous,
        "changed_leaf_count": {"cold": len(changed_cold), "edit": len(changed_edit)},
        "reachable_leaf_count": {"cold": len(cold_closure), "edit": len(edit_closure)},
        "outside_closure_leaf_count": {
            "cold": len(outside_cold),
            "edit": len(outside_edit),
        },
        "outside_closure_leaf_refs": {
            "cold": sorted(outside_cold)[:16],
            "edit": sorted(outside_edit)[:16],
        },
        "source_edit_sentence_count": {
            "cold": len(cold_boundary),
            "edit": len(edit_boundary),
        },
        "scope": "fixture_and_contract_audit_not_universal_theorem_or_incremental_work_measurement",
    }


__all__ = ["compare_leaf_locality"]
