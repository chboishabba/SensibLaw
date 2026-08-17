"""Audit-only locality comparison for portable numeric semantic leaves.

This module is deliberately not a receipt authority. It compares two audit
projections emitted from the closed numeric authority and records whether the
semantic leaves that changed are reachable from the source edit boundary.

Correspondence is transport-first rather than value-first: source coordinates
are carried through the known edit and structural occurrence keys are matched
without using the semantic digest whose change the audit is trying to measure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class ContiguousEditTransport:
    """Exact coordinate transport outside one conservative changed interval.

    Any two source versions admit this representation by taking their maximal
    common prefix and suffix. Multiple disjoint edits are therefore safely
    collapsed into one larger changed interval rather than guessed through.
    """

    before_start: int
    before_end: int
    after_start: int
    after_end: int

    @property
    def delta(self) -> int:
        return (self.after_end - self.after_start) - (
            self.before_end - self.before_start
        )

    def after_span_to_before(self, start: int, end: int) -> tuple[int, int] | None:
        if end <= self.after_start:
            return start, end
        if start >= self.after_end:
            return start - self.delta, end - self.delta
        return None


def _contiguous_edit_transport(before: str, after: str) -> ContiguousEditTransport:
    prefix = 0
    limit = min(len(before), len(after))
    while prefix < limit and before[prefix] == after[prefix]:
        prefix += 1

    suffix = 0
    before_remaining = len(before) - prefix
    after_remaining = len(after) - prefix
    while (
        suffix < before_remaining
        and suffix < after_remaining
        and before[len(before) - 1 - suffix] == after[len(after) - 1 - suffix]
    ):
        suffix += 1

    return ContiguousEditTransport(
        before_start=prefix,
        before_end=len(before) - suffix,
        after_start=prefix,
        after_end=len(after) - suffix,
    )


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


def _affected_spans_exact(
    transport: ContiguousEditTransport,
) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
    return (
        ((transport.before_start, transport.before_end),),
        ((transport.after_start, transport.after_end),),
    )


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
    transport: ContiguousEditTransport | None,
) -> tuple[tuple[int, int], ...] | None:
    spans = _spans(row)
    if not spans:
        return None
    if transport is None:
        return spans
    mapped: list[tuple[int, int]] = []
    for start, end in spans:
        value = transport.after_span_to_before(start, end)
        if value is None:
            return None
        mapped.append(value)
    return tuple(mapped)


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


def _occurrence_discriminator(row: Mapping[str, Any]) -> str:
    # `occurrence_key` is produced from stable structural/provenance coordinates
    # only. Older audit projections fall back to the coarser shape and therefore
    # remain fail-closed when duplicates survive.
    return str(row.get("occurrence_key") or row.get("shape") or "")


def compare_leaf_locality(
    cold_audit: Mapping[str, Any],
    edit_audit: Mapping[str, Any],
    *,
    cold_text: str,
    edit_text: str,
) -> dict[str, Any]:
    """Compare audit leaves under exact conservative source-edit transport."""

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
    transport = _contiguous_edit_transport(cold_text, edit_text)
    cold_changed, edit_changed = _affected_spans_exact(transport)
    cold_boundary = _sentence_boundary(cold_audit, cold_changed)
    edit_boundary = _sentence_boundary(edit_audit, edit_changed)
    cold_closure = _seed_and_closure(cold_nodes, cold_boundary)
    edit_closure = _seed_and_closure(edit_nodes, edit_boundary)

    def group(
        nodes: Mapping[str, Mapping[str, Any]],
        mapping: ContiguousEditTransport | None,
    ) -> dict[tuple[str, str, tuple[tuple[int, int], ...]], list[str]]:
        grouped: dict[tuple[str, str, tuple[tuple[int, int], ...]], list[str]] = {}
        for ref, row in nodes.items():
            key = _source_key(row, mapping)
            if key is not None:
                grouped.setdefault(
                    (str(row.get("family")), _occurrence_discriminator(row), key), []
                ).append(ref)
        return grouped

    cold_groups, edit_groups = group(cold_nodes, None), group(edit_nodes, transport)
    pairs: dict[str, str] = {}
    # Record each unresolved candidate class once.  The source-free propagation
    # loop can revisit an unchanged ambiguity; we assess those only after it has
    # reached a fixed point, rather than accumulating intermediate candidates.
    ambiguous_classes: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for key in set(cold_groups) | set(edit_groups):
        left, right = cold_groups.get(key, ()), edit_groups.get(key, ())
        if len(left) == len(right) == 1:
            pairs[left[0]] = right[0]
        elif left and right:
            ambiguous_classes.add((tuple(sorted(left)), tuple(sorted(right))))

    # Source-free leaves (exports/proofs) become identifiable once their ordered
    # dependency structure is paired. Duplicate candidates remain indeterminate.
    for _ in range(len(cold_nodes) + len(edit_nodes)):
        additions: dict[str, str] = {}
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
                and _occurrence_discriminator(right) == _occurrence_discriminator(left)
                and tuple(right.get("dependencies") or ()) == left_dependencies
            ]
            if len(candidates) == 1:
                additions[left_ref] = candidates[0]
        if not additions:
            break
        pairs.update(additions)

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
            and _occurrence_discriminator(right) == _occurrence_discriminator(left)
            and tuple(right.get("dependencies") or ()) == left_dependencies
        ]
        if len(candidates) > 1:
            ambiguous_classes.add(((left_ref,), tuple(sorted(candidates))))

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
        if ambiguous_classes
        else "verified"
        if not outside_cold and not outside_edit
        else "violated"
    )

    eligible_cold = sum(1 for row in cold_nodes.values() if _spans(row))
    eligible_edit = sum(1 for row in edit_nodes.values() if _spans(row))
    matched_sourceful_cold = sum(
        1 for left_ref in pairs if _spans(cold_nodes[left_ref])
    )
    matched_sourceful_edit = sum(
        1 for right_ref in pairs.values() if _spans(edit_nodes[right_ref])
    )

    def family_coverage(
        nodes: Mapping[str, Mapping[str, Any]],
        matched: Iterable[str],
    ) -> dict[str, dict[str, int | float | None]]:
        families = sorted({str(row.get("family")) for row in nodes.values()})
        matched_refs = set(matched)
        result: dict[str, dict[str, int | float | None]] = {}
        for family in families:
            eligible = [
                ref
                for ref, row in nodes.items()
                if str(row.get("family")) == family and _spans(row)
            ]
            matched_count = sum(ref in matched_refs for ref in eligible)
            result[family] = {
                "matched_sourceful_leaf_count": matched_count,
                "transport_eligible_sourceful_leaf_count": len(eligible),
                "kappa_delta": ratio(matched_count, len(eligible)),
            }
        return result

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    return {
        "state": state,
        "claim_made": state == "verified",
        "matching_ambiguity_count": len(ambiguous_classes),
        "matching_ambiguous_leaf_count": len(
            {ref for group in ambiguous_classes for side in group for ref in side}
        ),
        "matched_leaf_count": len(pairs),
        "matched_sourceful_leaf_count": {
            "cold": matched_sourceful_cold,
            "edit": matched_sourceful_edit,
        },
        "transport_eligible_leaf_count": {
            "cold": eligible_cold,
            "edit": eligible_edit,
        },
        "transport_match_coverage": {
            "cold": ratio(matched_sourceful_cold, eligible_cold),
            "edit": ratio(matched_sourceful_edit, eligible_edit),
        },
        "transport_match_coverage_by_family": {
            "cold": family_coverage(cold_nodes, pairs),
            "edit": family_coverage(edit_nodes, pairs.values()),
        },
        "changed_leaf_count": {"cold": len(changed_cold), "edit": len(changed_edit)},
        "reachable_leaf_count": {"cold": len(cold_closure), "edit": len(edit_closure)},
        "closure_precision_proxy": {
            "cold": ratio(len(changed_cold & cold_closure), len(cold_closure)),
            "edit": ratio(len(changed_edit & edit_closure), len(edit_closure)),
        },
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
        "edit_transport": {
            "mode": "maximal-common-prefix-suffix-contiguous-exact",
            "before_changed_range": [transport.before_start, transport.before_end],
            "after_changed_range": [transport.after_start, transport.after_end],
            "net_character_delta": transport.delta,
        },
        "scope": "fixture_and_contract_audit_not_universal_theorem_or_incremental_work_measurement",
    }


__all__ = ["ContiguousEditTransport", "compare_leaf_locality"]
