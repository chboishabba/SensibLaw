from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping

from .wikidata import StatementBundle, load_windows


DISJOINTNESS_REPORT_SCHEMA_VERSION = "wikidata_disjointness_report/v1"


@dataclass(frozen=True)
class DisjointPair:
    holder_qid: str
    left_qid: str
    right_qid: str
    statement_value: str | None

    @property
    def pair_key(self) -> str:
        return f"{self.left_qid}|{self.right_qid}"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


def load_disjointness_slice(path: Path) -> dict[str, Any]:
    return _load_json(path)


def _label_map(payload: Mapping[str, Any]) -> dict[str, str]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return {}
    raw = metadata.get("label_map")
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(key): str(value)
        for key, value in raw.items()
        if key is not None and value is not None
    }


def _label(qid: str, labels: Mapping[str, str]) -> str:
    value = labels.get(qid)
    if isinstance(value, str) and value.strip():
        return value
    return qid


def _active_bundles(payload: Mapping[str, Any]) -> tuple[str, list[StatementBundle]]:
    windows = load_windows(payload)
    if len(windows) != 1:
        raise ValueError("disjointness report requires exactly one window in the input slice")
    window = windows[0]
    return window.window_id, [bundle for bundle in window.bundles if bundle.rank != "deprecated"]


def _qualifier_values(bundle: StatementBundle, property_pid: str) -> list[str]:
    for pid, values in bundle.qualifiers:
        if pid == property_pid:
            return [str(value) for value in values]
    return []


def _pairs_from_bundles(bundles: list[StatementBundle]) -> list[DisjointPair]:
    pairs: dict[tuple[str, str, str], DisjointPair] = {}
    for bundle in bundles:
        if bundle.property != "P2738":
            continue
        qualifier_items = sorted(set(_qualifier_values(bundle, "P11260")))
        if len(qualifier_items) < 2:
            continue
        statement_value = None if bundle.value is None else str(bundle.value)
        for left_qid, right_qid in combinations(qualifier_items, 2):
            key = (bundle.subject, left_qid, right_qid)
            pairs[key] = DisjointPair(
                holder_qid=bundle.subject,
                left_qid=left_qid,
                right_qid=right_qid,
                statement_value=statement_value,
            )
    return sorted(pairs.values(), key=lambda item: (item.holder_qid, item.left_qid, item.right_qid))


def _subclass_graph(bundles: list[StatementBundle]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for bundle in bundles:
        if bundle.property != "P279" or bundle.value is None:
            continue
        graph.setdefault(bundle.subject, set()).add(str(bundle.value))
    return graph


def _instance_map(bundles: list[StatementBundle]) -> dict[str, set[str]]:
    memberships: dict[str, set[str]] = {}
    for bundle in bundles:
        if bundle.property != "P31" or bundle.value is None:
            continue
        memberships.setdefault(bundle.subject, set()).add(str(bundle.value))
    return memberships


def _ancestor_index(graph: Mapping[str, set[str]]) -> dict[str, set[str]]:
    nodes = set(graph.keys())
    for parents in graph.values():
        nodes.update(parents)
    memo: dict[str, set[str]] = {}

    def visit(node: str, trail: set[str]) -> set[str]:
        cached = memo.get(node)
        if cached is not None:
            return cached
        if node in trail:
            return {node}
        parents = graph.get(node, set())
        ancestors = {node}
        for parent in parents:
            ancestors.add(parent)
            ancestors.update(visit(parent, trail | {node}))
        memo[node] = ancestors
        return ancestors

    return {node: visit(node, set()) for node in sorted(nodes)}


def _violates_pair(classes: set[str], pair: DisjointPair) -> bool:
    return pair.left_qid in classes and pair.right_qid in classes


def _ancestor_distances(graph: Mapping[str, set[str]], start: str) -> dict[str, int]:
    distances = {start: 0}
    frontier = [start]
    while frontier:
        node = frontier.pop(0)
        for parent in sorted(graph.get(node, set())):
            next_distance = distances[node] + 1
            previous = distances.get(parent)
            if previous is not None and previous <= next_distance:
                continue
            distances[parent] = next_distance
            frontier.append(parent)
    return distances


def project_wikidata_disjointness_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    window_id, bundles = _active_bundles(payload)
    labels = _label_map(payload)
    pairs = _pairs_from_bundles(bundles)
    subclass_graph = _subclass_graph(bundles)
    instance_map = _instance_map(bundles)
    ancestors = _ancestor_index(subclass_graph)

    disjoint_pairs = [
        {
            "pair_id": f"{pair.holder_qid}:{pair.left_qid}:{pair.right_qid}",
            "holder_qid": pair.holder_qid,
            "holder_label": _label(pair.holder_qid, labels),
            "left_qid": pair.left_qid,
            "left_label": _label(pair.left_qid, labels),
            "right_qid": pair.right_qid,
            "right_label": _label(pair.right_qid, labels),
            "statement_value": pair.statement_value,
            "qualifier_pid": "P11260",
            "property_pid": "P2738",
        }
        for pair in pairs
    ]

    subclass_violations: list[dict[str, Any]] = []
    class_violation_keys: set[tuple[str, str]] = set()
    subclass_nodes = sorted(ancestors)
    for class_qid in subclass_nodes:
        class_ancestors = ancestors.get(class_qid, {class_qid})
        for pair in pairs:
            if not _violates_pair(class_ancestors, pair):
                continue
            pair_key = pair.pair_key
            class_violation_keys.add((class_qid, pair_key))
            subclass_violations.append(
                {
                    "qid": class_qid,
                    "label": _label(class_qid, labels),
                    "pair_key": pair_key,
                    "left_qid": pair.left_qid,
                    "left_label": _label(pair.left_qid, labels),
                    "right_qid": pair.right_qid,
                    "right_label": _label(pair.right_qid, labels),
                    "holder_qid": pair.holder_qid,
                    "holder_label": _label(pair.holder_qid, labels),
                    "direct_parents": sorted(subclass_graph.get(class_qid, set())),
                    "ancestor_classes": sorted(class_ancestors),
                }
            )
    subclass_violations.sort(key=lambda item: (item["pair_key"], item["qid"]))

    culprit_classes = []
    for violation in subclass_violations:
        qid = str(violation["qid"])
        pair_key = str(violation["pair_key"])
        parents = subclass_graph.get(qid, set())
        if any((parent, pair_key) in class_violation_keys for parent in parents):
            continue
        culprit_classes.append(violation)
    culprit_class_lookup = {
        (str(item["qid"]), str(item["pair_key"])): item for item in culprit_classes
    }

    for violation in subclass_violations:
        qid = str(violation["qid"])
        pair_key = str(violation["pair_key"])
        if (qid, pair_key) in culprit_class_lookup:
            violation["explained_by_culprit_class_qid"] = None
            continue
        candidate_culprits = [
            culprit_qid
            for culprit_qid, culprit_pair_key in culprit_class_lookup
            if culprit_pair_key == pair_key and culprit_qid in violation["ancestor_classes"]
        ]
        if candidate_culprits:
            distances = _ancestor_distances(subclass_graph, qid)
            chosen = min(candidate_culprits, key=lambda item: (distances.get(item, 10**9), item))
            violation["explained_by_culprit_class_qid"] = chosen
        else:
            violation["explained_by_culprit_class_qid"] = None

    instance_violations: list[dict[str, Any]] = []
    culprit_items: list[dict[str, Any]] = []
    for item_qid in sorted(instance_map):
        direct_classes = sorted(instance_map[item_qid])
        distances_by_direct_class = {
            class_qid: _ancestor_distances(subclass_graph, class_qid) for class_qid in direct_classes
        }
        inferred_classes: set[str] = set()
        for class_qid in direct_classes:
            inferred_classes.update(ancestors.get(class_qid, {class_qid}))
        for pair in pairs:
            if not _violates_pair(inferred_classes, pair):
                continue
            pair_key = pair.pair_key
            candidate_culprits = [
                culprit_qid
                for culprit_qid, culprit_pair_key in culprit_class_lookup
                if culprit_pair_key == pair_key and culprit_qid in inferred_classes
            ]
            explained_by = None
            if candidate_culprits:
                best: tuple[int, str] | None = None
                for culprit_qid in candidate_culprits:
                    distances = [
                        mapping.get(culprit_qid)
                        for mapping in distances_by_direct_class.values()
                        if culprit_qid in mapping
                    ]
                    if distances:
                        candidate = (min(distances), culprit_qid)
                        if best is None or candidate < best:
                            best = candidate
                if best is not None:
                    explained_by = best[1]
            item_record = {
                "qid": item_qid,
                "label": _label(item_qid, labels),
                "pair_key": pair_key,
                "left_qid": pair.left_qid,
                "left_label": _label(pair.left_qid, labels),
                "right_qid": pair.right_qid,
                "right_label": _label(pair.right_qid, labels),
                "holder_qid": pair.holder_qid,
                "holder_label": _label(pair.holder_qid, labels),
                "direct_instance_of": direct_classes,
                "inferred_classes": sorted(inferred_classes),
                "explained_by_culprit_class_qid": explained_by,
            }
            instance_violations.append(item_record)
            if explained_by is None:
                culprit_items.append(item_record)

    instance_violations.sort(key=lambda item: (item["pair_key"], item["qid"]))
    culprit_items.sort(key=lambda item: (item["pair_key"], item["qid"]))

    for culprit in culprit_classes:
        culprit_qid = str(culprit["qid"])
        pair_key = str(culprit["pair_key"])
        culprit["downstream_subclass_violation_count"] = sum(
            1
            for violation in subclass_violations
            if violation["pair_key"] == pair_key
            and violation["qid"] != culprit_qid
            and violation.get("explained_by_culprit_class_qid") == culprit_qid
        )
        culprit["downstream_instance_violation_count"] = sum(
            1
            for violation in instance_violations
            if violation["pair_key"] == pair_key
            and violation.get("explained_by_culprit_class_qid") == culprit_qid
        )

    review_summary = {
        "disjoint_pair_count": len(disjoint_pairs),
        "subclass_violation_count": len(subclass_violations),
        "instance_violation_count": len(instance_violations),
        "culprit_class_count": len(culprit_classes),
        "culprit_item_count": len(culprit_items),
    }

    return {
        "schema_version": DISJOINTNESS_REPORT_SCHEMA_VERSION,
        "source_window_id": window_id,
        "bounded_slice": {
            "properties": ["P2738", "P11260", "P279", "P31"],
            "active_statement_count": len(bundles),
        },
        "disjoint_pairs": disjoint_pairs,
        "subclass_violation_count": len(subclass_violations),
        "instance_violation_count": len(instance_violations),
        "subclass_violations": subclass_violations,
        "instance_violations": instance_violations,
        "culprit_classes": culprit_classes,
        "culprit_items": culprit_items,
        "review_summary": review_summary,
    }


__all__ = [
    "DISJOINTNESS_REPORT_SCHEMA_VERSION",
    "load_disjointness_slice",
    "project_wikidata_disjointness_payload",
]
