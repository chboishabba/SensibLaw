from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Mapping

from .wikidata import StatementBundle, load_windows
from .wikidata_disjointness import project_wikidata_disjointness_payload


DISJOINT_UNION_ANALYSIS_SCHEMA_VERSION = "wikidata_disjoint_union_analysis/v1"


@dataclass(frozen=True)
class DisjointUnionSpec:
    holder_qid: str
    member_qids: tuple[str, ...]
    statement_value: str | None

    @property
    def spec_id(self) -> str:
        return f"{self.holder_qid}:" + "|".join(self.member_qids)


def _active_bundles(payload: Mapping[str, Any]) -> tuple[str, list[StatementBundle]]:
    windows = load_windows(payload)
    if len(windows) != 1:
        raise ValueError("disjoint-union analysis requires exactly one window in the input slice")
    window = windows[0]
    return window.window_id, [bundle for bundle in window.bundles if bundle.rank != "deprecated"]


def _qualifier_values(bundle: StatementBundle, property_pid: str) -> list[str]:
    for pid, values in bundle.qualifiers:
        if pid == property_pid:
            return [str(value) for value in values]
    return []


def _specs(bundles: list[StatementBundle]) -> list[DisjointUnionSpec]:
    found: dict[tuple[str, tuple[str, ...], str | None], DisjointUnionSpec] = {}
    for bundle in bundles:
        if bundle.property != "P2738":
            continue
        members = tuple(sorted(set(_qualifier_values(bundle, "P11260"))))
        if not members:
            continue
        statement_value = None if bundle.value is None else str(bundle.value)
        key = (bundle.subject, members, statement_value)
        found[key] = DisjointUnionSpec(bundle.subject, members, statement_value)
    return sorted(found.values(), key=lambda spec: (spec.holder_qid, spec.member_qids))


def _subclass_graph(bundles: list[StatementBundle]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for bundle in bundles:
        if bundle.property == "P279" and bundle.value is not None:
            graph.setdefault(bundle.subject, set()).add(str(bundle.value))
    return graph


def _instance_map(bundles: list[StatementBundle]) -> dict[str, set[str]]:
    memberships: dict[str, set[str]] = {}
    for bundle in bundles:
        if bundle.property == "P31" and bundle.value is not None:
            memberships.setdefault(bundle.subject, set()).add(str(bundle.value))
    return memberships


def _ancestor_index(graph: Mapping[str, set[str]]) -> dict[str, set[str]]:
    nodes = set(graph)
    for parents in graph.values():
        nodes.update(parents)
    memo: dict[str, set[str]] = {}

    def visit(node: str, trail: set[str]) -> set[str]:
        if node in memo:
            return memo[node]
        if node in trail:
            return {node}
        out = {node}
        for parent in graph.get(node, set()):
            out.add(parent)
            out.update(visit(parent, trail | {node}))
        memo[node] = out
        return out

    return {node: visit(node, set()) for node in sorted(nodes)}


def _inferred_classes(
    direct: set[str] | list[str], ancestors: Mapping[str, set[str]]
) -> set[str]:
    out: set[str] = set()
    for class_qid in direct:
        out.update(ancestors.get(class_qid, {class_qid}))
    return out


def _label(qid: str, labels: Mapping[str, str]) -> str:
    label = labels.get(qid)
    return label if isinstance(label, str) and label.strip() else qid


def _label_map(payload: Mapping[str, Any]) -> dict[str, str]:
    metadata = payload.get("metadata")
    raw = metadata.get("label_map") if isinstance(metadata, Mapping) else None
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): str(value) for key, value in raw.items() if key is not None and value is not None}


def project_wikidata_disjoint_union_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Check the full finite-KB P2738 contract.

    This matches the scope of JMD's `Wikidata.dunOk_iff`: every listed member
    must be a subclass of the holder, every *known* instance of the holder must
    lie in at least one listed member, and distinct members must be pairwise
    disjoint on the known finite carrier.  It is not a closed-world claim about
    every possible real-world instance.
    """

    window_id, bundles = _active_bundles(payload)
    labels = _label_map(payload)
    specs = _specs(bundles)
    subclass_graph = _subclass_graph(bundles)
    instance_map = _instance_map(bundles)
    ancestors = _ancestor_index(subclass_graph)

    legacy = project_wikidata_disjointness_payload(payload)
    subclass_violations = legacy["subclass_violations"]
    instance_violations = legacy["instance_violations"]

    component_failures: list[dict[str, Any]] = []
    exhaustivity_failures: list[dict[str, Any]] = []
    pairwise_failures: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []

    inferred_items = {
        item: _inferred_classes(classes, ancestors)
        for item, classes in instance_map.items()
    }

    for spec in specs:
        component_rows: list[dict[str, Any]] = []
        for member in spec.member_qids:
            member_ancestors = ancestors.get(member, {member})
            if spec.holder_qid in member_ancestors:
                continue
            row = {
                "spec_id": spec.spec_id,
                "holder_qid": spec.holder_qid,
                "holder_label": _label(spec.holder_qid, labels),
                "member_qid": member,
                "member_label": _label(member, labels),
                "member_ancestor_classes": sorted(member_ancestors),
            }
            component_rows.append(row)
            component_failures.append(row)

        exhaustivity_rows: list[dict[str, Any]] = []
        for item in sorted(inferred_items):
            classes = inferred_items[item]
            if spec.holder_qid not in classes:
                continue
            if any(member in classes for member in spec.member_qids):
                continue
            row = {
                "spec_id": spec.spec_id,
                "holder_qid": spec.holder_qid,
                "holder_label": _label(spec.holder_qid, labels),
                "qid": item,
                "label": _label(item, labels),
                "direct_instance_of": sorted(instance_map.get(item, set())),
                "inferred_classes": sorted(classes),
                "listed_members": list(spec.member_qids),
            }
            exhaustivity_rows.append(row)
            exhaustivity_failures.append(row)

        pairwise_rows: list[dict[str, Any]] = []
        pair_keys = {
            f"{left}|{right}"
            for left, right in combinations(spec.member_qids, 2)
        }
        for kind, rows in (
            ("subclass", subclass_violations),
            ("instance", instance_violations),
        ):
            for violation in rows:
                if violation["holder_qid"] != spec.holder_qid or violation["pair_key"] not in pair_keys:
                    continue
                row = {
                    "spec_id": spec.spec_id,
                    "holder_qid": spec.holder_qid,
                    "holder_label": _label(spec.holder_qid, labels),
                    "pair_key": violation["pair_key"],
                    "violation_kind": kind,
                    "witness_qid": violation["qid"],
                    "witness_label": violation["label"],
                }
                pairwise_rows.append(row)
                pairwise_failures.append(row)

        components_ok = not component_rows
        coverage_ok = not exhaustivity_rows
        pairwise_ok = not pairwise_rows
        reports.append(
            {
                "spec_id": spec.spec_id,
                "holder_qid": spec.holder_qid,
                "holder_label": _label(spec.holder_qid, labels),
                "statement_value": spec.statement_value,
                "member_qids": list(spec.member_qids),
                "member_labels": [_label(member, labels) for member in spec.member_qids],
                "components_subclass_holder_ok": components_ok,
                "known_union_exhaustive_ok": coverage_ok,
                "pairwise_known_disjoint_ok": pairwise_ok,
                "finite_dun_ok": components_ok and coverage_ok and pairwise_ok,
                "component_not_subclass_count": len(component_rows),
                "union_exhaustivity_failure_count": len(exhaustivity_rows),
                "pairwise_disjointness_failure_count": len(pairwise_rows),
            }
        )

    component_failures.sort(key=lambda row: (row["spec_id"], row["member_qid"]))
    exhaustivity_failures.sort(key=lambda row: (row["spec_id"], row["qid"]))
    pairwise_failures.sort(
        key=lambda row: (row["spec_id"], row["pair_key"], row["violation_kind"], row["witness_qid"])
    )

    return {
        "schema_version": DISJOINT_UNION_ANALYSIS_SCHEMA_VERSION,
        "source_window_id": window_id,
        "semantics_scope": "known-entity finite-KB coverage; no closed-world exhaustivity claim",
        "disjoint_unions": reports,
        "component_not_subclass_of_union": component_failures,
        "union_exhaustivity_failures": exhaustivity_failures,
        "pairwise_disjointness_failures": pairwise_failures,
        "summary": {
            "disjoint_union_count": len(reports),
            "finite_dun_ok_count": sum(1 for row in reports if row["finite_dun_ok"]),
            "component_not_subclass_count": len(component_failures),
            "union_exhaustivity_failure_count": len(exhaustivity_failures),
            "pairwise_disjointness_failure_count": len(pairwise_failures),
        },
        "legacy_disjointness_summary": legacy["review_summary"],
    }


__all__ = [
    "DISJOINT_UNION_ANALYSIS_SCHEMA_VERSION",
    "project_wikidata_disjoint_union_payload",
]
